from sqlalchemy import create_engine, values
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import select
from sqlalchemy.orm import relationship
from sqlalchemy import desc
import datetime
from sqlalchemy import func
import math


# Create a SQLite database in memory for testing
engine = create_engine(f"sqlite:///keeper.db")

# Define base for model classes
Base = declarative_base()

# Create a session
session = Session(engine)

# Character database object
class Character(Base):
    __tablename__ = 'character'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    ap = Column(Integer, default=0)
    rp = Column(Integer, default=0)
    player = Column(Integer)

    transactions = relationship('Transaction', cascade="all, delete",
                                passive_deletes=True)


# Transaction database object
class Transaction(Base):
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey('character.id', ondelete='CASCADE'))
    amount = Column(Integer)
    currency = Column(String())
    user = Column(Integer)
    reason = Column(String(100))
    date = Column(DateTime)


# If the tables don't exist, create them
Base.metadata.create_all(engine)


# Create new character in database
def create_character(name, player):
    try:
        character = Character(name=name, player=player)
        session.add(character)
    except:
        session.rollback()
        return False
    else:
        session.commit()
        return True


# Delete a character
def delete_character(name):
    try:
        character = get_character_by_name(name)

        if not character:
            return False

        transactions = get_all_character_transactions(name)

        for transaction in transactions:
            session.delete(transaction)

        session.delete(character)
    except:
        session.rollback()
        return False
    else:
        session.commit()
        return True


# Erase a transaction and refund it
def erase_transaction(transaction_id):
    try:
        transaction = get_transaction_by_id(transaction_id)

        if not transaction:
            return False

        if transaction.currency == "AP":
            session.query(Character).where(Character.id == transaction.character_id).update(
                {Character.ap: Character.ap + transaction.amount})
        elif transaction.currency == "RP":
            session.query(Character).where(Character.id == transaction.character_id).update(
                {Character.ap: Character.ap + transaction.amount})

        session.delete(transaction)
    except:
        session.rollback()
        return False
    else:
        session.commit()
        return True

# Do a transaction and modify the associated character's currency appropriately
def do_transaction(character_name, user, currency, amount, reason):
    try:
        character = get_character_by_name(character_name)

        if not character:
            return False

        if currency == "AP":
            if amount < 0:
                if character.ap + amount < 0:
                    return False


            transaction = Transaction(character_id=character.id, currency=currency, amount=amount, user=user,
                                      reason=reason, date=datetime.datetime.now(datetime.timezone.utc))
            session.add(transaction)
            session.query(Character).where(Character.id == character.id).update({Character.ap: Character.ap + amount})
        elif currency == "RP":
            if amount < 0:
                if character.rp + amount < 0:
                    return False


            transaction = Transaction(character_id=character.id, currency=currency, amount=amount, user=user,
                                      reason=reason, date=datetime.datetime.now(datetime.timezone.utc))
            session.add(transaction)
            session.query(Character).where(Character.id == character.id).update({Character.rp: Character.rp + amount})
    except:
        session.rollback()
        return False
    else:
        session.commit()
        return True


# Get a character by name
def get_character_by_name(name) -> Character:
    result = session.execute(select(Character).where(Character.name == name)).first()
    if result:
        return result[0]
    else:
        return None

# Get a character by id
def get_character_by_id(char_id) -> Character:
    result = session.execute(select(Character).where(Character.id == char_id)).first()
    if result:
        return result[0]
    else:
        return None


# Get a character by transaction id
def get_character_by_transaction_id(transaction_id) -> Character:
    transaction = get_transaction_by_id(transaction_id)
    character = session.execute(select(Character).where(Character.id == transaction.character_id)).first()
    if character:
        return character[0]
    else:
        return None


# Get a character by name
def get_transaction_by_id(transaction_id) -> Transaction:
    result =  session.execute(select(Transaction).where(Transaction.id == transaction_id)).first()
    if result:
        return result[0]
    else:
        return None


# Get all characters a player has
def get_characters_by_owner(player):
    return session.execute(select(Character).where(Character.player == player)).all()


# Get all characters
def get_all_characters(page, page_size, currency):
    if currency == "AP":
        return session.execute(select(Character).order_by(
            desc(Character.ap), func.lower(Character.name)).limit(page_size).offset(page_size * (page - 1))).all()

    elif currency == "RP":
        return session.execute(select(Character).order_by(
            desc(Character.rp), func.lower(Character.name)).limit(page_size).offset(page_size * (page - 1))).all()

    else:
        return session.execute(select(Character).order_by(
            func.lower(Character.name)).limit(page_size).offset(page_size * (page - 1))).all()


def get_all_character_pages(page_size):
    return math.ceil(session.query(func.count(Character.id)).scalar() / page_size)


# Get paginated transactions by character name
def get_character_transactions(name, page, page_size):
    character = get_character_by_name(name)

    if not character:
        return False

    return session.query(Transaction).where(Transaction.character_id == character.id).order_by(
        desc(Transaction.date)).limit(page_size).offset(page_size * (page - 1)).all()


# Get all transactions by character name
def get_all_character_transactions(name):
    character = get_character_by_name(name)

    if not character:
        return False

    return session.query(Transaction).where(Transaction.character_id == character.id).order_by(
        desc(Transaction.date)).all()


# Get transactions by character name
def get_character_transaction_pages(name, page_size):
    character = get_character_by_name(name)

    if not character:
        return False

    return math.ceil(session.query(func.count(Transaction.id)).where(
        Transaction.character_id == character.id).scalar() / page_size)