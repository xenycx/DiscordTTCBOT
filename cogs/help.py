import discord
from discord.ext import commands
from discord.ui import View, Button

class NavigationButton(Button):
    def __init__(self, style, emoji, label, custom_id, row):
        super().__init__(style=style, emoji=emoji, label=label, custom_id=custom_id, row=row, disabled=False)
        
class NavigationView(View):
    def __init__(self, help_command):
        super().__init__(timeout=60.0)  # Changed to 60 seconds timeout
        self.help_command = help_command
        self.current_page = 1
        self.message = None  # Store message reference
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        max_pages = self.help_command.get_max_pages()
        
        # First page button
        first_button = NavigationButton(
            style=discord.ButtonStyle.primary,
            emoji="⏮️",
            label="პირველი",
            custom_id="first",
            row=0
        )
        first_button.disabled = self.current_page == 1
        
        # Previous button
        prev_button = NavigationButton(
            style=discord.ButtonStyle.primary,
            emoji="◀️",
            label="წინა",
            custom_id="previous",
            row=0
        )
        prev_button.disabled = self.current_page == 1
        
        # Next button
        next_button = NavigationButton(
            style=discord.ButtonStyle.primary,
            emoji="▶️",
            label="შემდეგი",
            custom_id="next",
            row=0
        )
        next_button.disabled = self.current_page == max_pages
        
        # Last button
        last_button = NavigationButton(
            style=discord.ButtonStyle.primary,
            emoji="⏭️",
            label="ბოლო",
            custom_id="last",
            row=0
        )
        last_button.disabled = self.current_page == max_pages

        # Add buttons if they're not at their respective limits
        if self.current_page > 1:
            self.add_item(first_button)
            self.add_item(prev_button)
        if self.current_page < max_pages:
            self.add_item(next_button)
            self.add_item(last_button)

        for button in self.children:
            button.callback = self.button_callback

    async def button_callback(self, interaction: discord.Interaction):
        try:
            if interaction.data["custom_id"] == "first":
                self.current_page = 1
            elif interaction.data["custom_id"] == "previous":
                self.current_page = max(1, self.current_page - 1)
            elif interaction.data["custom_id"] == "next":
                self.current_page = min(self.help_command.get_max_pages(), self.current_page + 1)
            elif interaction.data["custom_id"] == "last":
                self.current_page = self.help_command.get_max_pages()

            self.update_buttons()
            await self.help_command.show_page(interaction, self.current_page, self)
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ დაფიქსირდა შეცდომა: {str(e)}",
                ephemeral=True
            )

    async def on_timeout(self):
        """Disable buttons when the view times out"""
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(
                content="*დროის ლიმიტი ამოიწურა. გამოიყენეთ `/help` ბრძანება ხელახლა.*",
                view=self
            )
        except:
            pass

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.categories = {
            "🚌 ტრანსპორტი": ["bus", "buses", "stops", "stop", "stopinfo"],
            "🤖 AI": ["ask", "history", "clear_history"],
            "ℹ️ სისტემური": ["help", "ping", "uptime"],
            "📊 სტატისტიკა": ["stats"]
        }

    def categorize_commands(self, commands):
        # Create category-based dictionary
        categorized = {cat: [] for cat in self.categories.keys()}
        categorized["🔧 სხვა"] = []  # Other category

        # Sort commands into categories
        for command in commands:
            category = next((cat for cat, cmds in self.categories.items() 
                           if command.name in cmds), "🔧 სხვა")
            categorized[category].append(command)

        # Remove empty categories
        return {k: v for k, v in categorized.items() if v}

    def get_max_pages(self):
        commands = self.bot.tree.get_commands()
        categorized = self.categorize_commands(commands)
        return len(categorized)  # Number of non-empty categories

    async def show_page(self, interaction, page, view):
        try:
            commands = sorted(self.bot.tree.get_commands(), key=lambda x: x.name)
            categorized = self.categorize_commands(commands)
            categories = list(categorized.keys())
            total_pages = len(categories)

            if page > total_pages:
                page = total_pages

            current_category = categories[page - 1]
            category_commands = categorized[current_category]

            embed = discord.Embed(
                title="📚 ხელმისაწვდომი ბრძანებები",
                description=f"**გვერდი {page}/{total_pages}**\n{current_category}",
                color=discord.Color.blue()
            )

            for command in category_commands:
                embed.add_field(
                    name=f"/{command.name}",
                    value=f"```{command.description or 'აღწერის გარეშე'}```",
                    inline=False
                )

            embed.set_footer(text=f"გვერდი {page}/{total_pages}")
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ დაფიქსირდა შეცდომა: {str(e)}",
                ephemeral=True
            )

    @discord.app_commands.command(name="help", description="📚 ბრძანებების სია და დახმარება")
    async def help(self, interaction: discord.Interaction):
        try:
            view = NavigationView(self)
            commands = sorted(self.bot.tree.get_commands(), key=lambda x: x.name)
            categorized = self.categorize_commands(commands)
            categories = list(categorized.keys())
            total_pages = len(categories)
            current_category = categories[0]
            category_commands = categorized[current_category]

            embed = discord.Embed(
                title="📚 ხელმისაწვდომი ბრძანებები",
                description=f"**გვერდი 1/{total_pages}**\n{current_category}",
                color=discord.Color.blue()
            )

            for command in category_commands:
                embed.add_field(
                    name=f"/{command.name}",
                    value=f"```{command.description or 'აღწერის გარეშე'}```",
                    inline=False
                )

            embed.set_footer(text=f"გვერდი 1/{total_pages}")
            message = await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()

        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ დაფიქსირდა შეცდომა: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Help(bot))