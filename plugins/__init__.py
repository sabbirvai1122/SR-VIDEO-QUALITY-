# Don't Remove Credit @Fair033838 
# Subscribe YouTube Channel For Amazing Bot @newnatokmoviehere 
# Ask Doubt on telegram @ss_anime_box 

from aiohttp import web
from .route import routes

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app
