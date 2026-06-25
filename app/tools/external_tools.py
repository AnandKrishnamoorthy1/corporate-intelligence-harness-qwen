"""External tool integrations for business workflows."""

import requests
from typing import Dict, Any, Optional
from datetime import datetime

from loguru import logger
from config.settings import settings


class FinancialDataTools:
    """Real financial data tool integration using Alpha Vantage API."""
    
    def __init__(self):
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.timeout = 10
        
    def get_stock_data(self, ticker: str) -> Dict[str, Any]:
        """
        Invoke REAL Alpha Vantage API to get stock data.
        
        This is a real external tool call, not mocked data.
        Returns live market data for Qwen analysis.
        
        Args:
            ticker: Stock symbol (e.g., "NVDA", "TSLA")
            
        Returns:
            Dict with stock data including price, change, volume, etc.
            Falls back to mock data if API is unavailable.
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not set. Using mock data.")
            logger.info("To use real data, set ALPHA_VANTAGE_API_KEY in .env")
            return self._mock_stock_data(ticker)
        
        try:
            logger.info(f"[EXTERNAL TOOL] Fetching REAL stock data for {ticker} from Alpha Vantage API...")
            
            # Get latest quote from Alpha Vantage
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": ticker.upper(),
                "apikey": self.api_key,
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check if we got valid data
            if "Global Quote" not in data or not data["Global Quote"]:
                logger.warning(f"No data returned from Alpha Vantage for {ticker}")
                return self._mock_stock_data(ticker)
            
            quote = data["Global Quote"]
            
            # Parse response
            try:
                price = float(quote.get("05. price", 0))
                change = float(quote.get("09. change", 0))
                change_percent_str = quote.get("10. change percent", "0").rstrip("%")
                change_percent = float(change_percent_str) if change_percent_str else 0.0
                volume = int(quote.get("06. volume", 0))
                timestamp = quote.get("07. latest trading day", "")
                
            except (ValueError, TypeError):
                logger.warning("Error parsing Alpha Vantage response")
                return self._mock_stock_data(ticker)
            
            result = {
                "ticker": ticker.upper(),
                "price": price,
                "change": change,
                "change_percent": change_percent,
                "volume": volume,
                "timestamp": timestamp,
                "data_source": "Alpha Vantage (REAL API)",
                "fetched_at": datetime.now().isoformat(),
            }
            
            logger.info(f"[EXTERNAL TOOL SUCCESS] Retrieved REAL data: {result}")
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"Alpha Vantage API timeout for {ticker}")
            logger.info("Falling back to mock data")
            return self._mock_stock_data(ticker)
            
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to Alpha Vantage API")
            logger.info("Falling back to mock data")
            return self._mock_stock_data(ticker)
            
        except Exception as e:
            logger.error(f"Alpha Vantage API error: {type(e).__name__}: {str(e)}")
            logger.info("Falling back to mock data")
            return self._mock_stock_data(ticker)
    
    def _mock_stock_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fallback mock data when API fails or key is not set.
        
        In production, this would trigger an alert for missing/failed API integration.
        """
        return {
            "ticker": ticker.upper(),
            "price": 150.25,
            "change": 5.50,
            "change_percent": 3.8,
            "volume": 45_000_000,
            "timestamp": datetime.now().strftime("%Y-%m-%d"),
            "data_source": "Mock (API unavailable - configure ALPHA_VANTAGE_API_KEY)",
            "fetched_at": datetime.now().isoformat(),
            "note": "This is mock data. Connect real Alpha Vantage API for production use."
        }


# Global instance
financial_tools = FinancialDataTools()
