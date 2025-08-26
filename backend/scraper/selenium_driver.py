"""
Selenium WebDriver Manager for BaseballPATH Scrapers
Handles browser setup, configuration, and utilities
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

load_dotenv()

class SeleniumDriverManager:
    """Manages Chrome WebDriver instance with college scraping optimizations"""
    
    def __init__(self, headless: bool = True, delay: float = 2.0, timeout: int = 10):
        """
        Initialize Chrome WebDriver with college scraping settings
        
        Args:
            headless: Run browser without GUI
            delay: Default delay between requests (seconds)
            timeout: Default timeout for element waits (seconds)
        """
        self.headless = headless
        self.delay = delay
        self.timeout = timeout
        self.driver = None
        self.wait = None
        
        self._setup_driver()
    
    def _setup_driver(self):
        """Configure and launch Chrome WebDriver"""
        chrome_options = Options()
        
        # Basic options
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # College website compatibility
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Window and user agent settings
        chrome_options.add_argument("--window-size=1920,1080")
        user_agent = os.getenv("USER_AGENT", 
                              "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, self.timeout)
            
            # Execute script to hide automation flags
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Chrome WebDriver: {e}")
    
    def get(self, url: str, custom_delay: float = None) -> bool:
        """
        Navigate to URL with automatic delay and error handling
        
        Args:
            url: Target URL
            custom_delay: Override default delay
            
        Returns:
            bool: Success status
        """
        try:
            self.driver.get(url)
            time.sleep(custom_delay or self.delay)
            return True
        except Exception as e:
            print(f"Failed to load {url}: {e}")
            return False
    
    def find_element_safe(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = None) -> tuple:
        """
        Safely find element with timeout and error handling
        
        Args:
            selector: CSS selector or XPath
            by: Selenium By method
            timeout: Override default timeout
            
        Returns:
            tuple: (element, success_bool)
        """
        try:
            wait_time = timeout or self.timeout
            element = WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((by, selector))
            )
            return element, True
        except TimeoutException:
            return None, False
    
    def find_elements_safe(self, selector: str, by: By = By.CSS_SELECTOR) -> list:
        """
        Safely find multiple elements
        
        Args:
            selector: CSS selector or XPath
            by: Selenium By method
            
        Returns:
            list: Elements found (empty list if none)
        """
        try:
            return self.driver.find_elements(by, selector)
        except Exception:
            return []
    
    def extract_text_safe(self, element) -> str:
        """
        Safely extract text from element
        
        Args:
            element: Selenium WebElement
            
        Returns:
            str: Cleaned text or empty string
        """
        try:
            return element.text.strip() if element else ""
        except Exception:
            return ""
    
    def page_contains_keywords(self, keywords: list) -> bool:
        """
        Check if current page contains any of the given keywords
        
        Args:
            keywords: List of keywords to search for
            
        Returns:
            bool: True if any keyword found
        """
        try:
            page_source = self.driver.page_source.lower()
            return any(keyword.lower() in page_source for keyword in keywords)
        except Exception:
            return False
    
    def scroll_to_load_content(self, scroll_pause_time: float = 1.0, max_scrolls: int = 3):
        """
        Scroll page to trigger lazy loading of content
        
        Args:
            scroll_pause_time: Pause between scrolls
            max_scrolls: Maximum number of scroll attempts
        """
        try:
            for i in range(max_scrolls):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time)
        except Exception as e:
            print(f"Scroll error: {e}")
    
    def get_current_url(self) -> str:
        """Get current page URL"""
        try:
            return self.driver.current_url
        except Exception:
            return ""
    
    def get_page_title(self) -> str:
        """Get current page title"""
        try:
            return self.driver.title
        except Exception:
            return ""
    
    def close(self):
        """Close WebDriver and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Utility functions
def normalize_text(text: str) -> str:
    """Normalize text for consistent processing"""
    if not text:
        return ""
    return " ".join(text.strip().split())

def is_valid_grade(text: str) -> bool:
    """Check if text looks like a valid grade (A+, B-, etc.)"""
    if not text or len(text) > 3:
        return False
    return text[0].upper() in 'ABCDF' and (len(text) == 1 or text[1] in '+-')

def clean_numeric_value(text: str) -> str:
    """Clean numeric values (percentages, enrollment, etc.)"""
    if not text:
        return ""
    # Remove extra whitespace and normalize
    cleaned = normalize_text(text)
    return cleaned if cleaned else ""