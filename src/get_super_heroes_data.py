import requests
import random
import typer
import time
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

app = typer.Typer()
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def fetch_character_data(
    session: requests.Session,
    base_url: str,
    character_id: int,
    retries: int = 3,
    backoff_factor: float = 0.5
) -> Optional[Tuple[str, str]]:
    """
    Fetch character data with retry and exponential backoff using the provided session.

    :param session: A requests.Session object to reuse connections.
    :param base_url: The base URL of the Superhero API.
    :param character_id: The ID of the superhero character.
    :param retries: Maximum number of retries before giving up.
    :param backoff_factor: Factor controlling the exponential backoff delay.
    :return: Tuple of (name, gender) if the data is valid; otherwise, None.
    """
    url = f"{base_url}{character_id}"
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                name = data.get("name")
                gender = data.get("appearance", {}).get("gender")
                if name and gender and gender != "-":
                    return name, gender
                logger.debug(f"Invalid or incomplete data for ID {character_id}: {data}")
                return None  # Data is valid but does not match the filter
            else:
                logger.warning(f"Attempt {attempt}: Received status code {response.status_code} for ID {character_id}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt} failed for ID {character_id}: {e}")
        # Exponential backoff with jitter
        sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
        time.sleep(sleep_time)
    return None


@app.command()
def get_data(
    token: str = typer.Option(
        ...,
        prompt="Enter your access token from https://superheroapi.com/",
        hide_input=True
    ),
    max_workers: int = typer.Option(20, help="Number of threads for parallel execution")
):
    """
    Fetch superhero names and genders using the Superhero API,
    create a DataFrame of valid responses, and display gender distribution.
    """
    base_url = f"https://superheroapi.com/api/{token}/"
    data_list = []

    logger.info("Starting data fetch using ThreadPoolExecutor...")
    start_time = time.time()

    # Use a session for HTTP connection pooling
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(fetch_character_data, session, base_url, i): i 
                for i in range(1, 731)
            }
            for future in as_completed(future_to_id):
                result = future.result()
                if result:
                    data_list.append(result)

    elapsed = time.time() - start_time
    logger.info(f"Fetched {len(data_list)} records in {elapsed:.2f} seconds. Creating DataFrame...")

    # Create DataFrame and compute gender distribution
    df = pd.DataFrame(data_list, columns=["name", "gender"])
    gender_distribution = df['gender'].value_counts().reset_index()
    gender_distribution.columns = ['gender', 'count']

    typer.echo("\nGender distribution:")
    typer.echo(gender_distribution.to_string(index=False))


if __name__ == "__main__":
    app()
