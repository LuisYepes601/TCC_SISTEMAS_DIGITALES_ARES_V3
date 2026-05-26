"""core/services/services_service.py"""
import os
from core.data.services_repository import fetch_services, start_service as _s, stop_service as _st
def is_services_available(): return os.name == "nt"
def get_services(): return fetch_services()
def start_service(name): return _s(name.strip()) if name and name.strip() else (False, "Nombre vacío.")
def stop_service(name):  return _st(name.strip()) if name and name.strip() else (False, "Nombre vacío.")
