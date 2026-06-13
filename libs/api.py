import requests
import time
import logging

logger = logging.getLogger("airflow.task")

class SalicAPI:
    BASE_URL = "https://api.salic.cultura.gov.br/api/v1"

    def __init__(self, max_retries=3, retry_delay=5):
        self.session = requests.Session()
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def check_connectivity(self):
        """Check connection to the SALIC API base URL by sending a request."""
        url = f"{self.BASE_URL}/projetos/segmentos"
        try:
            # We fetch a lightweight path or simply hit the base URL to verify responsiveness
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Connectivity check failed for {url}: {e}")
            return False

    def get_data(self, endpoint, params=None):
        """Generic method to fetch data from a given endpoint with retry logic."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        if params is None:
            params = {}
        params['format'] = 'json'

        attempt = 0
        while attempt <= self.max_retries:
            try:
                response = self.session.get(url, params=params, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                # Intercept 404 response (usually means empty page / no records found on SALIC API)
                if e.response is not None and e.response.status_code == 404:
                    try:
                        error_json = e.response.json()
                        message = error_json.get("message", "")
                        logger.info(f"API returned 404 (No results found) for {url}: {message}. Treating as empty page.")
                    except Exception:
                        logger.info(f"API returned 404 (Not Found) for {url}. Treating as empty page.")
                    
                    endpoint_key = endpoint.split('/')[-1]
                    return {
                        '_embedded': {endpoint_key: []},
                        'total': 0
                    }

                attempt += 1
                if attempt <= self.max_retries:
                    # Exponential backoff
                    wait_time = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"Error fetching data from {url}: {e}. Retrying in {wait_time}s (attempt {attempt}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error fetching data from {url}: {e}. Max retries ({self.max_retries}) exceeded.")
                    return None


class CulturalSegments(SalicAPI):
    def fetch_all(self):
        return self.get_data("projetos/segmentos")


class Projects(SalicAPI):
    def fetch_page(self, segment_code, offset=0, limit=100):
        params = {
            'segmento': segment_code,
            'offset': offset,
            'limit': limit
        }
        return self.get_data("projetos", params)


class Proposals(SalicAPI):
    def fetch_page(self, offset=0, limit=100):
        params = {
            'offset': offset,
            'limit': limit
        }
        return self.get_data("propostas", params)


class Suppliers(SalicAPI):
    def fetch_page(self, offset=0, limit=100):
        params = {
            'offset': offset,
            'limit': limit
        }
        return self.get_data("fornecedores", params)


class Incentivizers(SalicAPI):
    def fetch_page(self, offset=0, limit=100):
        params = {
            'offset': offset,
            'limit': limit
        }
        return self.get_data("incentivadores", params)


class Proponents(SalicAPI):
    def fetch_page(self, offset=0, limit=100):
        params = {
            'offset': offset,
            'limit': limit
        }
        return self.get_data("proponentes", params)

