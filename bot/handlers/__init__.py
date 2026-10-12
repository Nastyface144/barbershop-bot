from aiogram import Router

from bot.handlers import admin, appointments, booking, common, fallback


def get_routers() -> list[Router]:
    # Порядок важен: админский роутер раньше общего, fallback — последним
    return [admin.router, common.router, booking.router, appointments.router, fallback.router]
