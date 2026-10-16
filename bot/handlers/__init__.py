from aiogram import Router

from bot.handlers import admin, appointments, booking, common, fallback, payments


def get_routers() -> list[Router]:
    # Порядок важен: админский роутер раньше общего, fallback — последним
    return [admin.router, common.router, booking.router, appointments.router, payments.router, fallback.router]
