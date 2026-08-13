from .showtix import ShowTix

async def setup(bot):
    await bot.add_cog(ShowTix(bot))
