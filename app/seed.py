"""Fictitious demo data so a fresh deployment doesn't look empty.

Every demo account uses the password ``DEMO_PASSWORD``.
"""

import random
from datetime import date, datetime, time, timedelta

import click

from . import db
from .models import Item, User

DEMO_PASSWORD = "lostandfound"

USERS = [
    ("maya_r", "Maya Rodriguez"),
    ("jkim", "Jordan Kim"),
    ("priya_s", "Priya Shah"),
    ("devon_t", "Devon Thomas"),
    ("lin_wei", "Lin Wei"),
    ("sam_okafor", "Sam Okafor"),
    ("alex_m", "Alex Moreno"),
    ("hannah_b", "Hannah Becker"),
]

# (title, description, location, photo seed)
ITEMS = [
    ("Black North Face backpack", "Has a keychain shaped like a cactus and a calculus textbook inside. Left with the front desk.", "Library, 2nd floor study carrels", "backpack"),
    ("AirPods Pro case (white)", "Just the case, with one earbud in it. Engraved with the initials “K.L.”", "Student Union food court", "earbuds"),
    ("Blue Hydro Flask", "32 oz, covered in national park stickers. Small dent near the bottom.", "Rec Center, weight room", "bottle"),
    ("Silver car key fob (Toyota)", "Single key on a red lanyard that says “Go Broncos.”", "Parking Structure B, level 3", "keys"),
    ("Student ID card", "Name partially visible. Dropped at the library front desk — bring photo ID to collect.", "Library entrance turnstiles", "idcard"),
    ("Gray hoodie, size M", "Plain gray zip-up, no logos. Was hanging on a chair after the 9am lecture.", "Science Building, room 120", "hoodie"),
    ("TI-84 Plus calculator", "Name written on the back in silver Sharpie, but it's mostly rubbed off.", "Math Building, room 214", "calculator"),
    ("Prescription glasses, tortoiseshell", "In a brown hard case. Fairly strong prescription.", "Campus shuttle (Route 2)", "glasses"),
    ("Green umbrella", "Compact, auto-open. One spoke is a little bent.", "Engineering Center lobby", "umbrella"),
    ("Brown leather wallet", "No cash, but has a few cards. Turned in to Campus Safety; ask for it there.", "Main quad, near the fountain", "wallet"),
    ("MacBook charger (USB-C, 67W)", "Apple brick plus a 2m cable. Was plugged in at the outlet by the window.", "Library, 3rd floor quiet zone", "charger"),
    ("Spiral notebook — Organic Chem", "Purple five-subject notebook, very full of reaction mechanisms. Someone is going to miss this before the midterm.", "Chemistry Lab 3", "notebook"),
    ("Kindle Paperwhite", "Black, in a navy fabric cover. Battery is dead so I couldn't check whose it is.", "Café on the ground floor of the Union", "ereader"),
    ("Single gold hoop earring", "Small, about 2cm across. Found on the floor by the sinks.", "Rec Center locker room", "earring"),
    ("Red scarf", "Knit, long, slightly fuzzy. Smells like vanilla.", "Lecture Hall A, back row", "scarf"),
    ("Bike lock key", "Kryptonite brand key on a small carabiner.", "Bike racks outside the dining hall", "lockkey"),
    ("Basketball", "Spalding, says “Property of Hall 4” in marker.", "Outdoor courts", "basketball"),
    ("Pink phone case with cards", "Phone case only (no phone) with a debit card and a transit pass tucked in the back.", "Bus stop on Main Street", "phonecase"),
    ("Lab goggles", "Standard clear safety goggles with “DT” scratched into the strap.", "Biology Building, room 305", "goggles"),
    ("Navy blue baseball cap", "Embroidered sailboat on the front.", "Bleachers at the soccer field", "cap"),
    ("Wireless mouse (Logitech)", "Gray, no USB receiver with it unfortunately.", "Computer lab, Engineering 101", "mouse"),
    ("Silver bracelet", "Thin chain with a small star charm. Clasp works fine.", "Dining hall, near the salad bar", "bracelet"),
    ("Textbook: Intro to Psychology", "8th edition, highlighted in yellow and orange. There's a name inside the cover.", "Social Sciences, room 210", "textbook"),
    ("Yoga mat (teal)", "Rolled up with a velcro strap.", "Rec Center, studio 2", "yogamat"),
    ("Over-ear headphones", "Sony, black, in a soft carrying pouch.", "Library group study room 4", "headphones"),
    ("Water-damaged sketchbook", "Got rained on, but the drawings inside are amazing. Really hope I can return this one.", "Art Building courtyard", "sketchbook"),
    ("Car keys with Hello Kitty keychain", "Three keys plus a grocery loyalty tag.", "Parking Lot C", "carkeys"),
    ("Black puffer jacket", "Women's size S. Phone charger in the left pocket.", "Lecture Hall C", "jacket"),
    ("USB flash drive (32 GB)", "Blue SanDisk on a lanyard. I didn't open it; describe the files to claim it.", "Library printing station", "usb"),
    ("Running shoes, size 10", "Neon green Nikes left on a bench.", "Track & field locker area", "shoes"),
    ("Thermos lunch bag", "Insulated, plaid pattern. Lunch is gone (it had been a while).", "Business School lounge", "lunchbag"),
    ("Passport (blue cover)", "Turned in to Campus Safety immediately. Contact them with your full name.", "International Center front steps", "passport"),
    ("Retainer in a purple case", "Yes, really. It's clean and in its case.", "Dining hall, table by the window", "retainer"),
    ("Guitar pick tin", "Small Altoids tin full of guitar picks and a capo.", "Music Building practice room 6", "guitarpicks"),
    ("Stuffed bear keychain", "Tiny brown bear wearing a graduation cap. Looks well loved.", "Campus bookstore checkout", "teddy"),
    ("Apple Watch (rose gold)", "Pink sport band. Screen is locked. At Campus Safety.", "Rec Center pool deck", "watch"),
]

# Stable placeholder photos (the same seed always returns the same image).
PHOTO_URL = "https://picsum.photos/seed/{seed}/640/480"


def seed_data(rng=None):
    rng = rng or random.Random(42)
    users = []
    for username, name in USERS:
        u = User(username=username, display_name=name)
        u.set_password(DEMO_PASSWORD)
        users.append(u)
    db.session.add_all(users)

    today = date.today()
    for i, (title, desc, location, seed) in enumerate(ITEMS):
        found_on = today - timedelta(days=rng.randint(0, 45))
        created = datetime.combine(found_on, time(rng.randint(8, 20), rng.randint(0, 59)))
        item = Item(
            title=title,
            description=desc,
            location=location,
            found_on=found_on,
            # A few posts without photos, the way real users behave.
            photo_url=None if i % 7 == 3 else PHOTO_URL.format(seed=seed),
            owner=users[i % len(users)],
            created_at=created,
        )
        # Older posts are more likely to have been returned already.
        if rng.random() < 0.15 + (today - found_on).days / 90:
            item.is_returned = True
            item.returned_at = created + timedelta(days=rng.randint(1, 5))
        db.session.add(item)
    db.session.commit()
    return len(users), len(ITEMS)


def seed_if_empty():
    if db.session.query(User.id).first() is None:
        seed_data()


def register_cli(app):
    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Drop all tables first. Deletes all data!")
    def seed_command(reset):
        """Load fictitious demo data."""
        if reset:
            db.drop_all()
            db.create_all()
        elif db.session.query(User.id).first() is not None:
            click.echo("Database already has data; use --reset to wipe and reseed.")
            return
        n_users, n_items = seed_data()
        click.echo(f"Seeded {n_users} users and {n_items} items. Demo password: {DEMO_PASSWORD}")
