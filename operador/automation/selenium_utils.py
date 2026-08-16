#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitários Selenium para automação do Cliente Operador Tasy
"""

import time
import logging
from typing import List, Tuple, Optional, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

logger = logging.getLogger("TasyOperador.SeleniumUtils")

def validar_e_localizar_elemento(driver, by: By, value: str, timeout: int = 15):
    """
    Verifica continuamente em tempo real se um elemento está visível e clicável.
    Retorna o elemento se estiver pronto, ou None se o tempo máximo for atingido.
    """
    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    except TimeoutException:
        logger.error(f"❌ Validação falhou: Elemento não ficou visível e clicável em {timeout}s. Seletor: {by}={value}")
        return None
    except Exception as e:
        logger.error(f"❌ Erro inesperado durante validação do elemento {by}={value}: {e}")
        return None

# As funções antigas wait_for_element e wait_for_clickable são removidas
# e substituídas pela nova função acima.

def safe_click(driver, element) -> bool:
    """Clica em um elemento de forma segura usando JavaScript."""
    try:
        if element:
            # Rola para o elemento e clica com JavaScript para maior robustez
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            driver.execute_script("arguments[0].click();", element)
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao clicar com JS: {e}")
        return False

def safe_send_keys(element, text: str) -> bool:
    """Envia texto para um elemento de forma segura usando JavaScript."""
    try:
        if element:
            driver = element._parent
            driver.execute_script("arguments[0].value = arguments[1];", element, text)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao enviar texto com JS: {e}")
        return False

def wait_for_page_load(driver, timeout: int = 30):
    """Espera a página carregar completamente"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except Exception as e:
        logger.error(f"Timeout aguardando carregamento da página: {e}")
        return False

def check_for_errors(driver) -> List[str]:
    """Verifica se há mensagens de erro na página"""
    errors = []
    try:
        # Seletores comuns para mensagens de erro
        error_selectors = [
            "div.error",
            "div.alert-danger",
            "div.msg-error",
            "span.error",
            ".error-message",
            "[id*='error']",
            "[class*='error']"
        ]
        
        for selector in error_selectors:
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in error_elements:
                    if element.is_displayed() and element.text.strip():
                        errors.append(element.text.strip())
            except:
                continue
                
    except Exception as e:
        logger.error(f"Erro ao verificar mensagens de erro: {e}")
    
    return errors

def take_screenshot(driver, filename: str = None) -> Optional[str]:
    """Tira screenshot da página"""
    try:
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        
        if driver.save_screenshot(filename):
            logger.info(f"Screenshot salvo: {filename}")
            return filename
        return None
        
    except Exception as e:
        logger.error(f"Erro ao tirar screenshot: {e}")
        return None

def scroll_to_element(driver, element):
    """Faz scroll até um elemento"""
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        return True
    except Exception as e:
        logger.error(f"Erro ao fazer scroll: {e}")
        return False

def wait_for_text_change(driver, element, original_text: str, timeout: int = 10) -> bool:
    """Espera o texto de um elemento mudar"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: element.text != original_text
        )
        return True
    except Exception as e:
        logger.error(f"Texto não mudou: {e}")
        return False

def get_element_text_safe(element) -> str:
    """Obtém texto de um elemento de forma segura"""
    try:
        if element:
            return element.text.strip()
        return ""
    except Exception as e:
        logger.error(f"Erro ao obter texto: {e}")
        return ""

def is_element_visible(driver, by: By, value: str) -> bool:
    """Verifica se um elemento está visível"""
    try:
        element = driver.find_element(by, value)
        return element.is_displayed()
    except:
        return False

def aguardar_invisibilidade(driver, by: By, value: str, timeout: int = 20) -> bool:
    """
    Verifica continuamente em tempo real até que um elemento se torne invisível.
    Retorna True se o elemento desaparecer, ou False se o tempo máximo for atingido.
    """
    try:
        logger.info(f"   ...aguardando desaparecimento do elemento: {by}={value}")
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((by, value))
        )
        logger.info(f"   ...elemento desapareceu.")
        return True
    except TimeoutException:
        logger.warning(f"⚠️  Elemento ainda estava visível após {timeout}s. Continuando mesmo assim. Seletor: {by}={value}")
        return False # Retorna False, mas o log indica que pode não ser um erro fatal

def wait_for_url_change(driver, current_url: str, timeout: int = 10) -> bool:
    """Espera a URL mudar"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url != current_url
        )
        return True
    except Exception as e:
        logger.error(f"URL não mudou: {e}")
        return False

def execute_script_safe(driver, script: str, *args) -> Any:
    """Executa JavaScript de forma segura"""
    try:
        return driver.execute_script(script, *args)
    except Exception as e:
        logger.error(f"Erro ao executar script: {e}")
        return None

def find_elements_safe(driver, by: By, value: str) -> List:
    """Encontra elementos de forma segura"""
    try:
        return driver.find_elements(by, value)
    except Exception as e:
        logger.error(f"Erro ao encontrar elementos: {e}")
        return []

def wait_for_invisibility(driver, by: By, value: str, timeout: int = 10):
    """Espera por um elemento desaparecer"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((by, value))
        )
        return True
    except Exception as e:
        logger.warning(f"Elemento ainda visível após timeout: {by}={value} - {e}")
        return False
