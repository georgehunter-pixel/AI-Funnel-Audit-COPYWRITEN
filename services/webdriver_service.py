import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from playwright.async_api import async_playwright, Browser, Page
import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import time
import base64

logger = logging.getLogger(__name__)

@dataclass
class InteractionResult:
    element_type: str
    element_selector: str
    element_text: str
    success: bool
    response_time: float
    error_message: Optional[str] = None
    screenshot_data: Optional[str] = None

@dataclass
class FormTestResult:
    form_selector: str
    fields_tested: int
    fields_successful: int
    submission_successful: bool
    validation_errors: List[str]
    response_time: float

class WebDriverManager:
    def __init__(self, headless: bool = True, max_drivers: int = 5):
        self.headless = headless
        self.max_drivers = max_drivers
        self.driver_pool = []
        self.available_drivers = []
        self.playwright_browser = None
        
    async def initialize_playwright(self):
        """Initialize Playwright browser"""
        if not self.playwright_browser:
            self.playwright = await async_playwright().start()
            self.playwright_browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
        return self.playwright_browser
    
    def create_chrome_driver(self) -> webdriver.Chrome:
        """Create a new Chrome WebDriver instance"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Disable images and CSS for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {str(e)}")
            raise
    
    async def get_driver(self) -> webdriver.Chrome:
        """Get an available WebDriver from the pool"""
        if self.available_drivers:
            return self.available_drivers.pop()
        
        if len(self.driver_pool) < self.max_drivers:
            driver = self.create_chrome_driver()
            self.driver_pool.append(driver)
            return driver
        
        # Wait for a driver to become available
        while not self.available_drivers:
            await asyncio.sleep(0.1)
        
        return self.available_drivers.pop()
    
    def release_driver(self, driver: webdriver.Chrome):
        """Return a WebDriver to the pool"""
        try:
            # Clear cookies and reset state
            driver.delete_all_cookies()
            driver.execute_script("window.localStorage.clear();")
            driver.execute_script("window.sessionStorage.clear();")
            self.available_drivers.append(driver)
        except Exception as e:
            logger.warning(f"Error releasing driver: {str(e)}")
            self.close_driver(driver)
    
    def close_driver(self, driver: webdriver.Chrome):
        """Close and remove a WebDriver from the pool"""
        try:
            driver.quit()
            if driver in self.driver_pool:
                self.driver_pool.remove(driver)
            if driver in self.available_drivers:
                self.available_drivers.remove(driver)
        except Exception as e:
            logger.warning(f"Error closing driver: {str(e)}")
    
    async def close_all(self):
        """Close all WebDrivers and cleanup"""
        for driver in self.driver_pool:
            try:
                driver.quit()
            except:
                pass
        
        self.driver_pool.clear()
        self.available_drivers.clear()
        
        if self.playwright_browser:
            await self.playwright_browser.close()
            await self.playwright.stop()

class InteractionTester:
    def __init__(self, driver_manager: WebDriverManager):
        self.driver_manager = driver_manager
        
    async def test_all_buttons(self, url: str) -> List[InteractionResult]:
        """Test all clickable buttons on a page"""
        driver = await self.driver_manager.get_driver()
        results = []
        
        try:
            logger.info(f"Testing buttons on {url}")
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Find all clickable elements
            clickable_selectors = [
                "button",
                "input[type='button']",
                "input[type='submit']",
                "a[href]",
                "[role='button']",
                ".btn",
                ".button"
            ]
            
            for selector in clickable_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for i, element in enumerate(elements[:10]):  # Limit to 10 per selector
                        if not element.is_displayed() or not element.is_enabled():
                            continue
                        
                        result = await self._test_button_click(driver, element, f"{selector}[{i}]")
                        results.append(result)
                        
                        # Small delay between clicks
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.warning(f"Error testing selector {selector}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to test buttons on {url}: {str(e)}")
        
        finally:
            self.driver_manager.release_driver(driver)
        
        return results
    
    async def _test_button_click(self, driver: webdriver.Chrome, element, selector: str) -> InteractionResult:
        """Test clicking a single button"""
        start_time = time.time()
        
        try:
            # Get element info
            element_text = element.text.strip() or element.get_attribute('value') or element.get_attribute('aria-label') or 'No text'
            
            # Scroll element into view
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            await asyncio.sleep(0.2)
            
            # Try to click
            original_url = driver.current_url
            element.click()
            
            # Wait a moment to see if anything happens
            await asyncio.sleep(1)
            
            response_time = time.time() - start_time
            
            # Check if URL changed or modal appeared
            new_url = driver.current_url
            url_changed = original_url != new_url
            
            # Check for modals or overlays
            modal_appeared = False
            try:
                modals = driver.find_elements(By.CSS_SELECTOR, ".modal, .popup, .overlay, [role='dialog']")
                modal_appeared = any(modal.is_displayed() for modal in modals)
            except:
                pass
            
            success = url_changed or modal_appeared
            
            return InteractionResult(
                element_type="button",
                element_selector=selector,
                element_text=element_text,
                success=success,
                response_time=response_time,
                error_message=None
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Take screenshot of error
            screenshot_data = None
            try:
                screenshot_data = driver.get_screenshot_as_base64()
            except:
                pass
            
            return InteractionResult(
                element_type="button",
                element_selector=selector,
                element_text=element_text or "Unknown",
                success=False,
                response_time=response_time,
                error_message=str(e),
                screenshot_data=screenshot_data
            )
    
    async def test_all_forms(self, url: str) -> List[FormTestResult]:
        """Test all forms on a page"""
        driver = await self.driver_manager.get_driver()
        results = []
        
        try:
            logger.info(f"Testing forms on {url}")
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Find all forms
            forms = driver.find_elements(By.TAG_NAME, "form")
            
            for i, form in enumerate(forms):
                if not form.is_displayed():
                    continue
                
                result = await self._test_form_submission(driver, form, f"form[{i}]")
                results.append(result)
                
                # Navigate back to original page for next form
                driver.get(url)
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Failed to test forms on {url}: {str(e)}")
        
        finally:
            self.driver_manager.release_driver(driver)
        
        return results
    
    async def _test_form_submission(self, driver: webdriver.Chrome, form, form_selector: str) -> FormTestResult:
        """Test submitting a single form"""
        start_time = time.time()
        
        try:
            # Scroll form into view
            driver.execute_script("arguments[0].scrollIntoView(true);", form)
            await asyncio.sleep(0.2)
            
            # Find all form inputs
            inputs = form.find_elements(By.CSS_SELECTOR, "input, select, textarea")
            
            fields_tested = 0
            fields_successful = 0
            validation_errors = []
            
            # Fill out form fields
            for input_elem in inputs:
                if not input_elem.is_displayed() or not input_elem.is_enabled():
                    continue
                
                try:
                    input_type = input_elem.get_attribute('type') or 'text'
                    input_name = input_elem.get_attribute('name') or ''
                    
                    # Generate test data based on input type
                    test_value = self._generate_test_data(input_type, input_name)
                    
                    if test_value and input_elem.tag_name.lower() != 'select':
                        input_elem.clear()
                        input_elem.send_keys(test_value)
                        fields_tested += 1
                        fields_successful += 1
                    elif input_elem.tag_name.lower() == 'select':
                        # Select first available option
                        options = input_elem.find_elements(By.TAG_NAME, "option")
                        if len(options) > 1:  # Skip first option (usually placeholder)
                            options[1].click()
                            fields_tested += 1
                            fields_successful += 1
                
                except Exception as e:
                    fields_tested += 1
                    validation_errors.append(f"Field error: {str(e)}")
            
            # Try to submit form
            submission_successful = False
            try:
                # Look for submit button
                submit_buttons = form.find_elements(By.CSS_SELECTOR, "input[type='submit'], button[type='submit'], button:not([type])")
                
                if submit_buttons:
                    original_url = driver.current_url
                    submit_buttons[0].click()
                    
                    # Wait for response
                    await asyncio.sleep(2)
                    
                    # Check if form was submitted (URL changed or success message appeared)
                    new_url = driver.current_url
                    url_changed = original_url != new_url
                    
                    # Check for success messages
                    success_indicators = driver.find_elements(By.CSS_SELECTOR, ".success, .thank-you, .confirmation")
                    success_message = any(elem.is_displayed() for elem in success_indicators)
                    
                    submission_successful = url_changed or success_message
            
            except Exception as e:
                validation_errors.append(f"Submission error: {str(e)}")
            
            response_time = time.time() - start_time
            
            return FormTestResult(
                form_selector=form_selector,
                fields_tested=fields_tested,
                fields_successful=fields_successful,
                submission_successful=submission_successful,
                validation_errors=validation_errors,
                response_time=response_time
            )
        
        except Exception as e:
            response_time = time.time() - start_time
            return FormTestResult(
                form_selector=form_selector,
                fields_tested=0,
                fields_successful=0,
                submission_successful=False,
                validation_errors=[str(e)],
                response_time=response_time
            )
    
    def _generate_test_data(self, input_type: str, input_name: str) -> str:
        """Generate appropriate test data for form fields"""
        input_name_lower = input_name.lower()
        
        if input_type == 'email' or 'email' in input_name_lower:
            return 'test@example.com'
        elif input_type == 'tel' or 'phone' in input_name_lower:
            return '+1234567890'
        elif input_type == 'url' or 'website' in input_name_lower:
            return 'https://example.com'
        elif input_type == 'number' or 'age' in input_name_lower:
            return '25'
        elif input_type == 'date':
            return '2024-01-01'
        elif 'name' in input_name_lower:
            if 'first' in input_name_lower:
                return 'John'
            elif 'last' in input_name_lower:
                return 'Doe'
            else:
                return 'John Doe'
        elif 'company' in input_name_lower:
            return 'Test Company'
        elif 'address' in input_name_lower:
            return '123 Test Street'
        elif 'city' in input_name_lower:
            return 'Test City'
        elif 'zip' in input_name_lower or 'postal' in input_name_lower:
            return '12345'
        elif input_type == 'password':
            return 'TestPassword123!'
        elif input_type == 'textarea' or input_name_lower in ['message', 'comment', 'description']:
            return 'This is a test message for form validation.'
        else:
            return 'Test Value'
    
    async def test_navigation_flow(self, start_url: str, max_depth: int = 3) -> Dict[str, Any]:
        """Test navigation flow and measure complexity"""
        driver = await self.driver_manager.get_driver()
        
        try:
            logger.info(f"Testing navigation flow from {start_url}")
            
            navigation_data = {
                'start_url': start_url,
                'pages_visited': [],
                'navigation_paths': [],
                'dead_ends': [],
                'conversion_paths': [],
                'average_clicks_to_convert': 0
            }
            
            # Start navigation test
            driver.get(start_url)
            await asyncio.sleep(2)
            
            # Find main navigation elements
            nav_elements = driver.find_elements(By.CSS_SELECTOR, "nav a, .menu a, .navigation a, header a")
            
            for nav_element in nav_elements[:5]:  # Limit to 5 nav items
                try:
                    if nav_element.is_displayed() and nav_element.is_enabled():
                        link_text = nav_element.text.strip()
                        href = nav_element.get_attribute('href')
                        
                        if href and href.startswith('http'):
                            # Test this navigation path
                            path_result = await self._test_navigation_path(driver, href, link_text, max_depth)
                            navigation_data['navigation_paths'].append(path_result)
                
                except Exception as e:
                    logger.warning(f"Error testing navigation element: {str(e)}")
            
            return navigation_data
        
        except Exception as e:
            logger.error(f"Failed to test navigation flow: {str(e)}")
            return {'error': str(e)}
        
        finally:
            self.driver_manager.release_driver(driver)
    
    async def _test_navigation_path(self, driver: webdriver.Chrome, url: str, link_text: str, max_depth: int) -> Dict[str, Any]:
        """Test a specific navigation path"""
        try:
            driver.get(url)
            await asyncio.sleep(1)
            
            # Check if this leads to a conversion page
            current_url = driver.current_url.lower()
            is_conversion_page = any(keyword in current_url for keyword in 
                                   ['checkout', 'cart', 'buy', 'purchase', 'order', 'signup', 'register'])
            
            # Count clicks needed to reach conversion
            clicks_to_convert = 0
            if not is_conversion_page and max_depth > 0:
                # Look for conversion-related links
                conversion_links = driver.find_elements(By.CSS_SELECTOR, 
                    "a[href*='checkout'], a[href*='cart'], a[href*='buy'], a[href*='signup']")
                
                if conversion_links:
                    clicks_to_convert = 1
                else:
                    clicks_to_convert = max_depth  # Assume max depth if no direct conversion found
            
            return {
                'link_text': link_text,
                'url': url,
                'is_conversion_page': is_conversion_page,
                'clicks_to_convert': clicks_to_convert,
                'page_title': driver.title
            }
        
        except Exception as e:
            return {
                'link_text': link_text,
                'url': url,
                'error': str(e)
            }