"""
Gerenciador de conexões WebSocket por room (uf:cargo).
"""
from collections import defaultdict
from typing import List


class ConnectionManager:
    def __init__(self):
        self.rooms: dict = defaultdict(list)

    async def connect(self, websocket, room: str) -> None:
        await websocket.accept()
        self.rooms[room].append(websocket)

    def disconnect(self, websocket, room: str) -> None:
        if websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)

    async def broadcast(self, room: str, message: str) -> None:
        for ws in list(self.rooms.get(room, [])):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws, room)
