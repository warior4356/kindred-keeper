# Load standard libraries
import discord
import yaml
from pathlib import Path
from discord.commands import Option

# Load project files
import database

# Loads and validates config file
def load_config(path):
    config_file = Path(path)
    if not config_file.is_file():
        print("File config.yml not found!")
        exit()

    loaded_config = yaml.safe_load(open(path))

    if "token" not in loaded_config.keys():
        print("Discord bot token not found!")
        exit()

    if "guild_ids" not in loaded_config.keys():
        print("Guild ids not found!")
        exit()

    if "gm_roles" not in loaded_config.keys():
        print("GM role not found!")
        exit()

    if "character_limit" not in loaded_config.keys():
        print("Character limit not found!")
        exit()

    if "page_size" not in loaded_config.keys():
        print("Page size not found!")
        exit()

    return loaded_config


# Define globals for the bot
bot = discord.Bot()
config = load_config("config.yml")


@bot.command(name="help", description="Displays potential commands and arguments", guild_ids=config["guild_ids"])
async def help_command(ctx):
    await ctx.respond("""Everyone:
/help - Displays this message
/info <character name> - Lists currency for a character, discord name of owner
/log <character name> <optional page number> - Lists the latest page of transactions for a character with id, currency change, date, and reason
/leaderboard <page> <optional currency to sort by> - Lists all characters by name, or by who has the most currency

Player only:
/create <character name> - Creates a character with the given name if it doesn't already exist

Player for only their characters and GMs for all characters:
/buy <character name> <AP/RP> <amount> <reason> - Logs a purchase for the given character
/refund <transaction id> - Refunds given transaction
/list <optional discord @mention of user> - Lists current characters

GMs only:
/add <character name> <AP/RP> <amount> <reason> - Logs given currency for a character
/remove <character name> <AP/RP> <amount> <reason> - Logs removed currency for a character
/delete <character name> - Deletes character and all transactions associated with it
/erase <transaction id> - Erases specific transaction and refunds currency spent on it""")


@bot.command(description="Gets information about a character", guild_ids=config["guild_ids"])
async def info(
        ctx,
        char_name: Option(str, name="character")
):
    character = database.get_character_by_name(char_name)
    player = await bot.fetch_user(character.player)

    response = "```Name                 |  AP |    RP | Player\n"
    response += (f"{character.name:<20} | " + f"{character.ap:>3} | " + f"{character.rp:>5} | " + f"{player.name}" + "\n")
    response += "```"

    await ctx.respond(response)

@bot.command(description="Lists a character's transactions", guild_ids=config["guild_ids"])
async def log(
        ctx,
        char_name: Option(str, name="character"),
        page: Option(int, description="Log page number", required=False, default=1)
):
    transactions = database.get_character_transactions(char_name, page, config["page_size"])
    pages = database.get_character_transaction_pages(char_name, config["page_size"])
    response = f"```Page {page}/{pages}\nID    | Type | Amount | Date       | User                             | Reason\n"

    for transaction in transactions:
        user = await bot.fetch_user(transaction.user)
        transaction_date = transaction.date.strftime("%Y-%m-%d")
        response += (f"{transaction.id:<5} | " + f"{transaction.currency:<4} | " +
                     f"{transaction.amount:<6} | " + f"{transaction_date} | "
                     + f"{user.name:<32} | " + f"{transaction.reason:<32}" + "\n")

    response += "```"
    await ctx.respond(response)


@bot.command(description="Lists all characters", guild_ids=config["guild_ids"])
async def leaderboard(
        ctx,
        page: Option(int, description="Log page number", required=False, default=1),
        currency: Option(str, choices=["AP", "RP"], description="Advancement Points or Royal Pieces", required=False),
):
    characters = database.get_all_characters(page, config["page_size"], currency)
    pages = database.get_all_character_pages(config["page_size"])
    response = f"```Page {page}/{pages}\nName                 |  AP |    RP | Player\n"

    for character in characters:
        player = await bot.fetch_user(character[0].player)
        response += (f"{character[0].name:<20} | " + f"{character[0].ap:>3} | " + f"{character[0].rp:>5} | " + f"{player.name}" + "\n")

    response += "```"
    await ctx.respond(response)

@bot.command(description="Creates a new character", guild_ids=config["guild_ids"])
async def create(
        ctx,
        char_name: Option(str, name="character")
):
    characters = database.get_characters_by_owner(ctx.author.id)

    if len(characters) >= config["character_limit"]:
        await ctx.respond(f"The limit is {config["character_limit"]} characters and you have {len(characters)} characters!")
        return

    if len(char_name) > 20:
        await ctx.respond(f"The character name length limit is 20 characters and yours is {len(char_name)} characters!")
        return

    if database.get_character_by_name(char_name):
        await ctx.respond(f"{char_name} already exists!")
        return

    if database.create_character(char_name, ctx.author.id):
        await ctx.respond(f"Successfully created {char_name}")
    else:
        await ctx.respond(f"Failed to create {char_name}")


@bot.command(name="list", description="Lists all of a player's characters", guild_ids=config["guild_ids"])
async def list_chars(
        ctx,
        player: Option(discord.User, name="player", required=False)
):


    if player:
        characters = database.get_characters_by_owner(player.id)
    else:
        characters = database.get_characters_by_owner(ctx.author.id)
    response = "```Name                 |  AP |    RP \n"

    for character in characters:
        response += (f"{character[0].name:<20} | " + f"{character[0].ap:>3} | " + f"{character[0].rp:>5}" + "\n")

    response += "```"
    await ctx.respond(response)


@bot.command(description="Creates a new character", guild_ids=config["guild_ids"])
async def buy(
        ctx,
        char_name: Option(str, name="character"),
        currency: Option(str, choices=["AP", "RP"], description="Advancement Points or Royal Pieces"),
        amount: Option(int, description="Amount you are spending"),
        reason: Option(str, description="What you are spending it on"),
):
    gm = False
    owned = False

    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    character = database.get_character_by_name(char_name)
    if character and character.player == ctx.author.id:
        owned = True

    if not gm and not owned:
        await ctx.respond(f"Begone player!")
        return

    if amount < 0:
        await ctx.respond(f"No stealing from the kingdom!")
        return

    if currency == "AP" and character.ap - amount < 0:
        await ctx.respond(f"Not enough AP!")
        return

    if currency == "RP" and character.rp - amount < 0:
        await ctx.respond(f"Not enough RP!")
        return

    if database.do_transaction(character.name, ctx.author.id, currency, (amount * -1), reason):
        await ctx.respond(f"{char_name} bought {reason} for {amount} {currency}")
    else:
        await ctx.respond(f"{char_name} failed to buy {reason} for {amount} {currency}")


@bot.command(description="Refunds a given transaction", guild_ids=config["guild_ids"])
async def refund(
        ctx,
        transaction_id: Option(int, name="transaction", description="Transaction id number to refund"),
):
    gm = False
    owned = False

    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    character = database.get_character_by_transaction_id(transaction_id)
    if character and character.player == ctx.author.id:
        owned = True

    if not gm and not owned:
        await ctx.respond(f"Begone player!")
        return

    transaction = database.get_transaction_by_id(transaction_id)

    if not transaction:
        await ctx.respond(f"Transaction {transaction_id} not found")
        return

    if database.do_transaction(character.name, ctx.author.id, transaction.currency, (transaction.amount * -1),
                               f"Refunded transaction {transaction_id}"):
        await ctx.respond(f"Refunded transaction {transaction_id}")
    else:
        await ctx.respond(f"Failed to refund transaction {transaction_id}")


@bot.command(description="Adds currency to a character", guild_ids=config["guild_ids"])
async def add(
        ctx,
        char_name: Option(str, name="character"),
        currency: Option(str, choices=["AP", "RP"], description="Advancement Points or Royal Pieces"),
        amount: Option(int, description="Amount you are spending"),
        reason: Option(str, description="What you are spending it on"),
):
    gm = False


    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    if not gm:
        await ctx.respond(f"Begone player!")
        return

    if not database.get_character_by_name(char_name):
        await ctx.respond(f"{char_name} not found")
        return

    if amount < 0:
        await ctx.respond(f"No stealing from the kingdom!")
        return

    if database.do_transaction(char_name, ctx.author.id, currency, amount, reason):
        await ctx.respond(f"Added {amount} {currency} to {char_name}")
    else:
        await ctx.respond(f"Failed to add {amount} {currency} to {char_name}")


@bot.command(description="Removes currency from a character", guild_ids=config["guild_ids"])
async def remove(
        ctx,
        char_name: Option(str, name="character"),
        currency: Option(str, choices=["AP", "RP"], description="Advancement Points or Royal Pieces"),
        amount: Option(int, description="Amount you are spending"),
        reason: Option(str, description="What you are spending it on"),
):
    gm = False


    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    if not gm:
        await ctx.respond(f"Begone player!")
        return

    character = database.get_character_by_name(char_name)

    if not character:
        await ctx.respond(f"{char_name} not found")
        return

    if amount < 0:
        await ctx.respond(f"No stealing from the kingdom!")
        return

    if currency == "AP" and character.ap - amount < 0:
        await ctx.respond(f"Not enough AP!")
        return

    if currency == "RP" and character.rp - amount < 0:
        await ctx.respond(f"Not enough RP!")
        return

    if database.do_transaction(char_name, ctx.author.id, currency, (amount * -1), reason):
        await ctx.respond(f"Removed {amount} {currency} from {char_name}")
    else:
        await ctx.respond(f"Failed to remove {amount} {currency} from {char_name}")


@bot.command(description="Deletes a character. THIS CANNOT BE UNDONE", guild_ids=config["guild_ids"])
async def delete(
        ctx,
        char_name: Option(str, name="character")
):

    gm = False

    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    if not gm:
        await ctx.respond(f"Begone player!")
        return

    if not database.get_character_by_name(char_name):
        await ctx.respond(f"{char_name} not found")
        return

    if database.delete_character(char_name):
        await ctx.respond(f"Deleted {char_name}")
    else:
        await ctx.respond(f"Failed to delete {char_name}")


@bot.command(description="Erases transaction and refunds currency gain/loss", guild_ids=config["guild_ids"])
async def erase(
        ctx,
        transaction: Option(int, description="Transaction id number to erase"),
):
    gm = False

    for role in ctx.author.roles:
        if role.id in config["gm_roles"]:
            gm = True

    if not gm:
        await ctx.respond(f"Begone player!")
        return

    if not database.get_transaction_by_id(transaction):
        await ctx.respond(f"{transaction} not found")
        return

    if database.erase_transaction(transaction):
        await ctx.respond(f"Erased {transaction}")
    else:
        await ctx.respond(f"Failed to erase {transaction}")


def main():
    bot.run(config["token"])


if __name__ == '__main__':
    main()