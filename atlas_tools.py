"""
Tools that Atlas can use. The AI model decides by itself when to call them,
based on each function's description (its docstring).

To add your own tool: write a function with type hints and a docstring
in the same style as the ones below, then add it to the TOOLS list at the bottom.
"""

import io
import subprocess
import threading
from datetime import datetime, timedelta

import psutil
import requests
from ddgs import DDGS
from PIL import ImageGrab

# Apps Atlas is allowed to open. Add your own: "name you say": "command".
APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "file explorer": "explorer",
    "vs code": "code",
    "visual studio code": "code",
    "chrome": "chrome",
    "edge": "msedge",
    "paint": "mspaint",
    "task manager": "taskmgr",
    "spotify": "spotify:",
    "settings": "ms-settings:",
}

# Short names for websites. Any other address like "bbc.com" also works.
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "wikipedia": "https://www.wikipedia.org",
    "maps": "https://maps.google.com",
}

# Called when a reminder goes off. voice_assistant.py and atlas_app.py
# replace this with a function that shows and speaks the reminder.
on_reminder = print

# A screenshot taken by look_at_screen() waits here until it is sent to the AI.
pending_images = []


def look_at_screen() -> str:
    """Take a screenshot of the user's screen so you can see it. Use this when the
    user asks about something on their screen, like an error, a page or a window.

    Returns:
        A note that the screenshot is attached.
    """
    image = ImageGrab.grab()
    image.thumbnail((1024, 1024))  # smaller image = much faster to process
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pending_images.append(buffer.getvalue())
    return "Screenshot taken, it is attached in the next message."


def open_app(name: str) -> str:
    """Open an app on the user's PC, for example notepad, calculator, file explorer,
    vs code, chrome, edge, paint, task manager, spotify or settings.

    Args:
        name: The app name, for example "vs code".

    Returns:
        Whether it worked.
    """
    command = APPS.get(name.strip().lower())
    if command is None:
        return f"I can't open '{name}'. Apps I can open: {', '.join(APPS)}."
    # Only fixed commands from the APPS list above are ever run.
    subprocess.Popen(["cmd", "/c", "start", "", command],
                     creationflags=subprocess.CREATE_NO_WINDOW)
    return f"Opened {name}."


def open_website(site: str) -> str:
    """Open a website in the user's web browser, for example youtube, gmail,
    or an address like "bbc.com".

    Args:
        site: A short name like "youtube" or a web address like "bbc.com".

    Returns:
        Whether it worked.
    """
    site = site.strip()
    url = WEBSITES.get(site.lower())
    if url is None:
        if " " in site or "." not in site:
            return f"I don't know the website '{site}'. Try its address, like example.com."
        url = site if site.startswith(("http://", "https://")) else "https://" + site
    if not url.startswith(("http://", "https://")):
        return "I can only open normal web addresses."
    subprocess.Popen(["cmd", "/c", "start", "", url], creationflags=subprocess.CREATE_NO_WINDOW)
    return f"Opened {url}."


def set_reminder(minutes: float, message: str) -> str:
    """Set a reminder. After the given number of minutes, Atlas will say the message
    out loud. Reminders are forgotten if Atlas is closed.

    Args:
        minutes: How many minutes from now, for example 20.
        message: What to remind the user about, for example "drink water".

    Returns:
        When the reminder will go off.
    """
    due = datetime.now() + timedelta(minutes=minutes)
    timer = threading.Timer(minutes * 60, lambda: on_reminder(message))
    timer.daemon = True  # don't keep the program running just for a reminder
    timer.start()
    return f"Reminder set for {due:%I:%M %p}: {message}"


def get_pc_info() -> str:
    """Get live information about this PC: CPU usage, RAM usage, free disk space
    and which programs use the most memory.

    Returns:
        A short summary of the PC's current state.
    """
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    # Add up memory per program name (Chrome, for example, runs many processes).
    memory_by_app = {}
    for process in psutil.process_iter(["name", "memory_info"]):
        info = process.info
        if info["memory_info"] and info["name"]:
            name = info["name"].removesuffix(".exe")
            memory_by_app[name] = memory_by_app.get(name, 0) + info["memory_info"].rss
    top = sorted(memory_by_app.items(), key=lambda item: item[1], reverse=True)[:5]
    top_text = ", ".join(f"{name} {size / 1e9:.1f} GB" for name, size in top)

    return (f"CPU usage: {cpu:.0f}%. "
            f"RAM: {ram.used / 1e9:.1f} of {ram.total / 1e9:.1f} GB used ({ram.percent:.0f}%). "
            f"Disk C: {disk.free / 1e9:.0f} GB free of {disk.total / 1e9:.0f} GB. "
            f"Programs using the most memory: {top_text}.")


WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def get_weather(city: str) -> str:
    """Get the current weather and the forecast for the next 3 days in a city.
    Needs the internet.

    Args:
        city: The city name, for example "London".

    Returns:
        The current weather and a short forecast.
    """
    # Free weather service, no account needed: https://open-meteo.com
    places = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": city, "count": 1}, timeout=10).json()
    if not places.get("results"):
        return f"I couldn't find a city called '{city}'."
    place = places["results"][0]

    weather = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 3,
    }, timeout=10).json()

    now = weather["current"]
    text = (f"Weather in {place['name']}, {place.get('country', '')}: "
            f"{WEATHER_CODES.get(now['weather_code'], 'unknown')}, {now['temperature_2m']:.0f}°C "
            f"(feels like {now['apparent_temperature']:.0f}°C), humidity {now['relative_humidity_2m']}%, "
            f"wind {now['wind_speed_10m']:.0f} km/h. Forecast:")
    daily = weather["daily"]
    for i, day in enumerate(daily["time"]):
        text += (f" {day}: {WEATHER_CODES.get(daily['weather_code'][i], 'unknown')}, "
                 f"{daily['temperature_2m_min'][i]:.0f} to {daily['temperature_2m_max'][i]:.0f}°C, "
                 f"{daily['precipitation_probability_max'][i]}% chance of rain.")
    return text


def web_search(query: str) -> str:
    """Search the web for current information, like news, prices, sports results,
    or anything that may have changed recently. Needs the internet.

    Args:
        query: What to search for, for example "bitcoin price today".

    Returns:
        The top search results with short descriptions.
    """
    results = DDGS().text(query, max_results=5)
    if not results:
        return "No results found."
    return "\n".join(f"- {r['title']}: {r['body']} ({r['href']})" for r in results)


# The tools Atlas can use. Remove one from this list to turn it off.
TOOLS = [look_at_screen, open_app, open_website, set_reminder,
         get_pc_info, get_weather, web_search]

TOOLS_BY_NAME = {tool.__name__: tool for tool in TOOLS}


def run_tool(name, arguments):
    """Run the tool the AI asked for and return its result as text."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"There is no tool called {name}."
    try:
        return str(tool(**arguments))
    except requests.RequestException:
        return "That needs the internet, and I couldn't connect. Check your connection."
    except Exception as e:
        return f"The tool {name} failed: {e}"
