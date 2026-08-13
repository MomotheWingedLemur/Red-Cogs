import discord
from redbot.core import commands, Config
from discord.ext import tasks
import datetime

class ShowTix(commands.Cog):
    """Manages monthly channel access and Camshow tickets."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8273645192, force_registration=True)
        
        default_guild = {
            "role_id": None,
            "thread_id": None,
            "message_id": None,
            "allowed_users": [],
            "last_cleared_month": datetime.datetime.now().month
        }
        self.config.register_guild(**default_guild)
        self.monthly_clear.start()

    def cog_unload(self):
        self.monthly_clear.cancel()

    async def update_thread_list(self, guild: discord.Guild):
        """Helper function to update the VIP guest list in the thread."""
        thread_id = await self.config.guild(guild).thread_id()
        msg_id = await self.config.guild(guild).message_id()
        users = await self.config.guild(guild).allowed_users()
        
        if not thread_id:
            return

        thread = guild.get_thread(thread_id)
        if not thread:
            return

        if not users:
            content = "🎟️ **Current VIP Guest List:**\n*The list is currently empty.*"
        else:
            user_mentions = [f"<@{uid}>" for uid in users]
            content = "🎟️ **Current VIP Guest List:**\n" + "\n".join(user_mentions)

        if msg_id:
            try:
                msg = await thread.fetch_message(msg_id)
                await msg.edit(content=content)
                return
            except discord.NotFound:
                pass 

        new_msg = await thread.send(content)
        await self.config.guild(guild).message_id.set(new_msg.id)

    @commands.group(aliases=["st"])
    @commands.admin()
    async def showtix(self, ctx):
        """Box office commands for managing VIP access."""
        pass

    @showtix.command()
    async def setup(self, ctx, role: discord.Role, thread: discord.Thread):
        """Set the VIP role and the thread to post the guest list in."""
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await self.config.guild(ctx.guild).thread_id.set(thread.id)
        
        await ctx.send(f"🎬 **Box office is open!** VIP role set to `{role.name}` and the guest list will be tracked in {thread.mention}.")
        await self.update_thread_list(ctx.guild)

    @showtix.command()
    async def setrole(self, ctx, role: discord.Role):
        """Link a new Discord role to the box office."""
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"🎫 **Role Linked!** I have attached the `{role.name}` role to the box office. When you use `[p]showtix add`, this is the ticket I will hand out.")

    @showtix.command()
    async def add(self, ctx, member: discord.Member):
        """Grant a user a VIP ticket."""
        role_id = await self.config.guild(ctx.guild).role_id()
        
        if not role_id:
            return await ctx.send("The box office isn't set up yet! Please link a role first.")

        role = ctx.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                return await ctx.send("I don't have permission to hand out that ticket. Make sure my bot role is higher than the VIP role.")

        async with self.config.guild(ctx.guild).allowed_users() as users:
            if member.id not in users:
                users.append(member.id)

        await self.update_thread_list(ctx.guild)
        await ctx.send(f"🎟️ **Admit One!** {member.mention} has been granted VIP access to the show. The guest list has been updated.")

    @showtix.command()
    async def remove(self, ctx, member: discord.Member):
        """Revoke a user's VIP ticket and remove them from the guest list."""
        role_id = await self.config.guild(ctx.guild).role_id()
        
        if not role_id:
            return await ctx.send("The box office isn't set up yet! Please link a role first.")

        async with self.config.guild(ctx.guild).allowed_users() as users:
            if member.id in users:
                users.remove(member.id)
            else:
                return await ctx.send(f"❌ {member.display_name} doesn't seem to be on the VIP guest list.")

        role = ctx.guild.get_role(role_id)
        if role:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                await ctx.send(f"⚠️ I couldn't remove the role from {member.mention} because my bot role isn't high enough, but I have removed them from the database list.")

        await self.update_thread_list(ctx.guild)
        await ctx.send(f"🚫 **Ticket Revoked!** {member.mention}'s VIP access has been canceled and the guest list has been updated.")

    @tasks.loop(hours=24)
    async def monthly_clear(self):
        """Background task that runs daily to check if the month has changed."""
        now = datetime.datetime.now()
        
        for guild_id in await self.config.all_guilds():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            last_month = await self.config.guild(guild).last_cleared_month()
            
            if now.month != last_month:
                role_id = await self.config.guild(guild).role_id()
                users = await self.config.guild(guild).allowed_users()
                
                role = guild.get_role(role_id)
                if role:
                    for user_id in users:
                        member = guild.get_member(user_id)
                        if member:
                            try:
                                await member.remove_roles(role)
                            except discord.Forbidden:
                                pass 

                await self.config.guild(guild).allowed_users.set([])
                await self.config.guild(guild).last_cleared_month.set(now.month)
                
                await self.update_thread_list(guild)
                
    @monthly_clear.before_loop
    async def before_monthly_clear(self):
        await self.bot.wait_until_red_ready()
