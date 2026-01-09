from contextlib import asynccontextmanager
from fastapi import FastAPI

from dndsim.db.init_db import init_db
from dndsim.api.routers.creatures import router as creatures_router
from dndsim.api.routers.encounters import router as encounters_router
from dndsim.api.routers.encounter_saves import router as encounter_saves_router
from dndsim.api.routers.encounter_runtime import router as encounter_runtime_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="DnD 5e Combat Simulator", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(creatures_router)
app.include_router(encounters_router)
app.include_router(encounter_saves_router)
app.include_router(encounter_runtime_router)
