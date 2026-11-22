"""Read-only next-meal planning. Recipes never become diary entries automatically."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from .schemas import Nutrition, StrictModel
from .timezones import timezone_info

MEALS = ("breakfast", "lunch", "dinner")


class FoodSuggestion(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=350)
    portion: str = Field(min_length=1, max_length=120)
    nutrition: Nutrition
    minutes: int = Field(ge=1, le=240)
    ingredients: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=2, max_length=16)
    steps: list[Annotated[str, Field(min_length=1, max_length=600)]] = Field(min_length=2, max_length=10)
    image_query: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z][A-Za-z ' -]+$")


class MealSuggestionContext(StrictModel):
    meal_type: Literal["breakfast", "lunch", "dinner", "extra"]
    meals_left: int = Field(ge=1, le=3)
    remaining: Nutrition | None = None
    budget: Nutrition | None = None


class RecipeImage(StrictModel):
    url: str
    source_url: str
    author: str
    license: str


class FoodSuggestionRead(FoodSuggestion):
    image: RecipeImage | None = None


def next_meal_context(snapshot, now=None):
    now = now or datetime.fromisoformat(snapshot.get("as_of") or datetime.now(timezone.utc).isoformat())
    zone = timezone_info(snapshot.get("timezone", "UTC"))
    local = now.astimezone(zone)
    start = 0 if local.hour < 11 else 1 if local.hour < 17 else 2
    recorded = set()
    for entry in snapshot.get("confirmed_food_today", []):
        data = entry.get("data", {})
        kind = data.get("meal_type")
        if not kind:
            instant = datetime.fromisoformat(entry["occurred_at"])
            hour = instant.astimezone(zone).hour
            kind = "breakfast" if hour < 11 else "lunch" if hour < 17 else "dinner"
        recorded.add(kind)
    upcoming = [kind for kind in MEALS[start:] if kind not in recorded]
    count = len(upcoming) or 1
    remaining = snapshot.get("remaining_nutrition")
    remaining = Nutrition.model_validate(remaining) if remaining is not None else None
    budget = Nutrition(**{key: (getattr(remaining, key) / Decimal(count)).quantize(Decimal("0.1")) for key in ("kcal", "protein", "fat", "carbs")}) if remaining else None
    return MealSuggestionContext(meal_type=upcoming[0] if upcoming else "extra", meals_left=count, remaining=remaining, budget=budget)


def suggestion_errors(output, context):
    recipes = output.nutrition_suggestions
    message = None
    if len(recipes) < 2:
        message = "Provide 2–3 complete alternative recipes in nutrition_suggestions, not only assistant_text."
    elif context.budget and context.budget.kcal > 0 and any(recipe.nutrition.kcal > context.budget.kcal * Decimal("1.15") + 25 for recipe in recipes):
        message = "Adjust recipe portions to next_meal.budget.kcal; alternatives must fit one upcoming meal, not the entire remaining day."
    elif any(recipe.nutrition.kcal <= 0 or abs(recipe.nutrition.kcal - (recipe.nutrition.protein * 4 + recipe.nutrition.fat * 9 + recipe.nutrition.carbs * 4)) > max(40, recipe.nutrition.kcal * Decimal("0.15")) for recipe in recipes):
        message = "Check each recipe's per-portion energy and macros: calories should approximately equal 4*protein + 9*fat + 4*carbs."
    if message:
        return [{"location": "nutrition_suggestions", "type": "recipe_validation", "message": message}]
    return []


async def illustrated_suggestions(recipes, *, client, bot_model, resource_recorder):
    from .recipe_photo_selection import select_recipe_photos
    images, usage = await select_recipe_photos(recipes, client=client, bot_model=bot_model, resource_recorder=resource_recorder)
    return [FoodSuggestionRead(**recipe.model_dump(), image=image).model_dump(mode="json") for recipe, image in zip(recipes, images)], usage
