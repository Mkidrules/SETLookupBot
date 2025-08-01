import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, ui, File
from dotenv import load_dotenv
import os
import asyncio
from uuid import uuid4
import time

from pdf_reader import search_pdfs, render_pdf_page_as_images

# Global variable to track last activity time
last_activity = time.time()

def update_last_activity():
    global last_activity
    last_activity = time.time()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = nextcord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)


async def idle_monitor(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(60)  # Check every minute
        if time.time() - last_activity > 600:  # 10 minutes
            print("Bot has been idle for 10 minutes.")

            # Optional: change status to idle
            await bot.change_presence(status=nextcord.Status.idle, activity=nextcord.Game("Sleeping..."))

            # Optional: clean up resources or temp files
            # e.g., delete old PDF images, close DB connections, etc.

            # Optional: wait until activity resumes before changing back
            while time.time() - last_activity > 600:
                await asyncio.sleep(30)

            # Resume status
            await bot.change_presence(status=nextcord.Status.online, activity=None)
            print("Bot is active again.")



class PDFSelectView(nextcord.ui.View):
    def __init__(self, options, interaction, results):
        super().__init__(timeout=60)
        self.options = options
        self.interaction = interaction
        self.results = results
        self.message = None

        self.select_menu = nextcord.ui.Select(
            placeholder="Select a PDF to view",
            options=options,
            min_values=1,
            max_values=1
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction: nextcord.Interaction):
        await interaction.response.defer()  # ✅ Prevents "interaction failed"

        selected_value = self.select_menu.values[0]
        selected_result = next((r for r in self.results if r[1] == selected_value), None)

        if selected_result:
            pdf_path, filename, page_num, _ = selected_result
            session_id = str(uuid4())
            output_dir = os.path.join("output", session_id)

            try:
                file_paths = render_pdf_page_as_images(pdf_path, page_num, output_folder=output_dir)
                embeds = []

                for i, path in enumerate(file_paths):
                    embed = Embed(title=f"{filename} - Page {page_num + 1} (Part {i + 1})")
                    embed.set_image(url=f"attachment://page_{i}.png")
                    embeds.append(embed)

                view = ImagePaginationView(embeds, file_paths, interaction.user)
                msg = await interaction.channel.send(embed=embeds[0], file=nextcord.File(file_paths[0], filename="page_0.png"), view=view)
                view.message = msg
                await self.message.delete()

            except Exception as e:
                await interaction.followup.send(f"❌ Error rendering PDF: {e}")

        self.stop()  # Optional: stop interaction timeout

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="⏰ Selection timed out.", view=None)
            except:
                pass



class ImagePaginationView(nextcord.ui.View):
    def __init__(self, embeds, file_paths, author: nextcord.User, timeout=120):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.file_paths = file_paths  # Store file paths instead of File objects
        self.author = author
        self.index = 0

    async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
        # Optional: only allow the command author to click the buttons
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You're not allowed to interact with this.", ephemeral=True)
            return False
        return True
    
    def get_file(self, index: int) -> nextcord.File:
        filename = f"page_{index}.png"
        return nextcord.File(self.file_paths[index], filename=filename)


    @nextcord.ui.button(label="Previous", style=nextcord.ButtonStyle.secondary)
    async def previous(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.index = (self.index - 1) % len(self.embeds)
        embed = self.embeds[self.index]
        filename = f"page_{self.index}.png"
        embed.set_image(url=f"attachment://{filename}")
        file = nextcord.File(self.file_paths[self.index], filename=filename)

        update_last_activity()
        # Delete old message and send a new one
        await interaction.message.delete()
        msg = await interaction.channel.send(embed=embed, file=file, view=self)
        self.message = msg  # ✅ Keep track of the new message

    @nextcord.ui.button(label="Next", style=nextcord.ButtonStyle.secondary)
    async def next(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.index = (self.index + 1) % len(self.embeds)
        embed = self.embeds[self.index]
        filename = f"page_{self.index}.png"
        embed.set_image(url=f"attachment://{filename}")
        file = nextcord.File(self.file_paths[self.index], filename=filename)

        update_last_activity()
        # Delete old message and send a new one
        await interaction.message.delete()
        msg = await interaction.channel.send(embed=embed, file=file, view=self)
        self.message = msg  # ✅ Keep track of the new message

    async def on_timeout(self):
        # Delete the message
        if hasattr(self, "message") and self.message:
            try:
                await self.message.delete()
            except nextcord.NotFound:
                print("Message already deleted.")
            except Exception as e:
                print(f"Failed to delete message: {e}")

        # Delete all files in the output directory
        try:
            output_dir = os.path.dirname(self.file_paths[0])
            for filename in os.listdir(output_dir):
                file_path = os.path.join(output_dir, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete file {file_path}: {e}")

            os.rmdir(output_dir)
        except Exception as e:
            print(f"Failed to delete folder {output_dir}: {e}")



@bot.slash_command(name="lookup", description="Search PDF content and show page images")
async def lookup(interaction: Interaction, term: str):
    await interaction.response.defer()

    results = search_pdfs("./pdfs", term)
    if not results:
        update_last_activity()
        await interaction.followup.send("❌ No results found.")
        return

    # Get unique PDFs with matches
    unique_files = {r[1]: r for r in results}
    
    if len(unique_files) == 1:
        # Only one match, proceed normally
        pdf_path, filename, page_num, _ = list(unique_files.values())[0]
        session_id = str(uuid4())
        output_dir = os.path.join("output", session_id)

        try:
            file_paths = render_pdf_page_as_images(pdf_path, page_num, output_folder=output_dir)
            embeds = []

            for i, path in enumerate(file_paths):
                embed = Embed(title=f"{filename} - Page {page_num + 1} (Part {i + 1})")
                embed.set_image(url=f"attachment://page_{i}.png")
                embeds.append(embed)

            view = ImagePaginationView(embeds, file_paths, interaction.user)
            update_last_activity()
            msg = await interaction.followup.send(embed=embeds[0], file=nextcord.File(file_paths[0], filename="page_0.png"), view=view)
            view.message = msg

        except Exception as e:
            await interaction.followup.send(f"❌ Error rendering PDF: {e}")

    else:
        # Multiple matches — ask user to pick
        options = [nextcord.SelectOption(label=name, value=name) for name in unique_files]

        # ✅ Limit to 25 options (Discord API limit)
        limited_options = options[:25]
        limited_file_data = list(unique_files.values())[:25]

        view = PDFSelectView(limited_options, interaction, limited_file_data)
        update_last_activity()
        msg = await interaction.followup.send("Multiple PDFs matched your term. Please choose one:", view=view)
        view.message = msg

        if len(options) > 25:
            await interaction.followup.send(f"⚠️ Showing only the first 25 of {len(options)} matching PDFs.")


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Start idle monitor
bot.loop.create_task(idle_monitor(bot))

bot.run(TOKEN)
