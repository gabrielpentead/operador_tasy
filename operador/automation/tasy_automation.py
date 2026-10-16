#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automação do sistema Tasy para o Cliente Operador
"""

import time
import base64
import logging
import threading
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automation.browser_manager import EdgeBrowserManager
from automation.voice_manager import VoiceManager
from automation.selenium_utils import validar_e_localizar_elemento, safe_click, safe_send_keys, aguardar_invisibilidade
from utils.constants import ERROR_CHECK_INTERVAL

logger = logging.getLogger("TasyOperador.TasyAutomation")

class TasyAutomation:
    """Classe que encapsula a lógica de automação para uma única instância (Monitor ou Totem)."""

    def __init__(self, usuario: str, senha: str, codigo_maquina: str, automation_type: str, 
                 tasy_url: str, debug_port: int, monitor_index: Optional[int] = None, 
                 websocket_client=None, on_status_change=None, config=None):
        self.usuario = usuario
        self.senha = senha
        self.codigo_maquina = codigo_maquina
        self.automation_type = automation_type
        self.tasy_url = tasy_url
        self.debug_port = debug_port
        self.monitor_index = monitor_index
        self.websocket_client = websocket_client
        self.on_status_change = on_status_change

        # Recebe o MESMO objeto de configuração do cliente. Sem isso, o
        # EdgeBrowserManager criava um OperadorConfig próprio, que lia o
        # config.ini na criação da automação e mantinha essa fotografia em
        # memória. Como save_config() grava o objeto inteiro, uma atualização
        # de driver depois de uma troca de senha regravava a senha ANTIGA por
        # cima da nova — a senha "voltava" sozinha horas depois.
        self.browser_manager = EdgeBrowserManager(config)
        self.voice_manager = VoiceManager(driver=None)
        
        self.browser_instance: Optional[Dict[str, Any]] = None
        self.driver: Optional[webdriver.Edge] = None
        self.status = "Inicializado"
        self.crashed = False  # Flag para indicar parada por falha
        self.stop_event = threading.Event()

    def _update_status(self, new_status: str):
        """Atualiza o status e notifica callback se houver."""
        self.status = new_status
        if self.on_status_change:
            try:
                self.on_status_change(self.automation_type, self.status)
            except Exception as e:
                logger.error(f"Erro ao notificar mudança de status: {e}")

    def _execute_automation_flow(self):
        """Executa a sequência de passos da automação, levantando uma exceção em caso de falha."""
        steps = [
            (self._step_acessar_site, "Acessar URL do Tasy"),
            (self._step_verificar_aviso_seguranca, "Verificar aviso de segurança"),
            (self._step_login_e_fechar_popups, "Realizar login e tratar popups"),
            (self._step_buscar_gerenciamento_senhas, "Navegar para 'Gerenciamento de Senhas'"),
            (self._step_select_automation_mode, "Selecionar modo de automação")
        ]

        for step_func, step_name in steps:
            if self.stop_event.is_set():
                logger.info(f"[{self.automation_type}] Parada solicitada antes do passo: {step_name}")
                return  # Parada controlada, não é um crash

            self._update_status(f"Executando: {step_name}")
            if not step_func():
                # Levanta uma exceção para que o bloco 'except' principal em 'run' possa capturá-la
                raise Exception(f"Falha no passo de automação: '{step_name}'")


    def run(self):
        self.crashed = False
        self.stop_event.clear()
        logger.info(f"🚀 [{self.automation_type}] Iniciando automação na porta {self.debug_port}.")

        try:
            self.browser_instance = self.browser_manager.start_browser(self.debug_port, self.monitor_index)
            if not self.browser_instance:
                raise Exception(f"Falha ao iniciar o navegador na porta {self.debug_port}")

            self.driver = self.browser_instance["driver"]
            self.voice_manager.set_driver(self.driver)
            self.voice_manager.speak(f"Iniciando {self.automation_type}.")

            # --- FLUXO DE AUTOMAÇÃO ---
            self._execute_automation_flow()
            # --- FIM DO FLUXO ---

            # Se a automação foi interrompida durante o fluxo, encerra a thread silenciosamente.
            if self.stop_event.is_set():
                return

            self._update_status(f"{self.automation_type} ativado")
            logger.info(f"✅ [{self.automation_type}] Automação ativada e em monitoramento.")
            self.voice_manager.speak(f"{self.automation_type} ativado.")

            # Loop de monitoramento de saúde pós-automação
            while not self.stop_event.is_set():
                self.stop_event.wait(ERROR_CHECK_INTERVAL)
                if not self._is_healthy():
                    if not self.stop_event.is_set():
                        self.crashed = True
                        break  # Sai do loop para o 'finally'
                # Leve e limitada a 1x por minuto internamente; nunca levanta exceção
                # nem interfere no resultado da saúde.
                self.voice_manager.verificar_voz()

        except Exception as e:
            # Se a parada não foi solicitada, é um erro crítico que deve ser registrado.
            if not self.stop_event.is_set():
                logger.error(f"❌ [{self.automation_type}] Erro crítico durante a execução: {e}", exc_info=True)
                self._update_status(f"Erro: {e}")
                self.crashed = True  # Sinaliza para o monitor de saúde que a automação falhou
        finally:
            logger.info(f"[{self.automation_type}] Thread de automação encerrada (crashed={self.crashed}).")
            self._internal_stop()

    def stop(self):
        """Sinaliza para a thread de automação parar."""
        logger.info(f"⏹️ [{self.automation_type}] Solicitando parada da automação...")
        self.stop_event.set()
        self._update_status("Parando...")

    def _internal_stop(self):
        """Lógica interna de parada, chamada pelo finally do run()."""
        if self.browser_instance:
            self.browser_manager.stop_browser(self.browser_instance)
            self.browser_instance = None
            self.driver = None
        self._update_status("Parado")
        logger.info(f"✅ [{self.automation_type}] Automação parada com sucesso.")

    # --- PASSOS DA AUTOMAÇÃO (AGORA COMO 'MISSÕES' AUTO-VALIDADAS) ---

    def _step_acessar_site(self) -> bool:
        logger.info(f"🤖 [{self.automation_type}] PASSO 1/5: Acessando URL do Tasy...")
        if self.tasy_url not in self.driver.current_url:
            self.driver.get(self.tasy_url)
        self._update_status("Site acessado")
        return True # Acesso ao site é bloqueante, então consideramos sucesso

    def _step_verificar_aviso_seguranca(self) -> bool:
        logger.info(f"🤖 [{self.automation_type}] PASSO 2/5: Verificando aviso de segurança...")
        # A verificação é opcional, então não falha se não encontrar
        details_button = validar_e_localizar_elemento(self.driver, By.ID, "details-button", timeout=3)
        if details_button:
            safe_click(self.driver, details_button)
            proceed_link = validar_e_localizar_elemento(self.driver, By.ID, "proceed-link", timeout=5)
            if not proceed_link:
                logger.error("Botão 'details' clicado, mas o link para prosseguir não foi encontrado.")
                return False
            safe_click(self.driver, proceed_link)

            # Validação mais robusta: aguarda pelo campo de usuário da página de login
            logger.info("   Aguardando página de login carregar após contornar aviso...")
            login_field = validar_e_localizar_elemento(self.driver, By.ID, "loginUsername", timeout=15)
            if not login_field:
                logger.error("Link para prosseguir foi clicado, mas a página de login não carregou corretamente.")
                return False

        self._update_status("Aviso de segurança verificado")
        return True

    def _step_login_e_fechar_popups(self) -> bool:
        logger.info(f"🤖 [{self.automation_type}] PASSO 3/5: Realizando login e tratando popups...")
        
        # Preencher campos e clicar em login
        user_field = validar_e_localizar_elemento(self.driver, By.ID, "loginUsername")
        if not user_field: return False
        safe_send_keys(user_field, self.usuario)

        pass_field = validar_e_localizar_elemento(self.driver, By.ID, "loginPassword")
        if not pass_field: return False
        safe_send_keys(pass_field, self.senha)

        login_button = validar_e_localizar_elemento(self.driver, By.CSS_SELECTOR, "input.btn-green.w-login-button")
        if not login_button: return False
        safe_click(self.driver, login_button)

        # Verificação de erro de login (Credenciais Inválidas)
        logger.info("   Verificando sucesso do login...")
        # Pequena pausa para o aviso aparecer
        time.sleep(1)
        
        # Procura por mensagem de erro comum
        try:
            # XPath genérico para mensagens de erro ou o texto específico relatado
            error_xpath = "//*[contains(text(), 'Usuário ou senha inválido') or contains(text(), 'User or password invalid')]"
            error_element = self.driver.find_elements(By.XPATH, error_xpath)
            if error_element and any(e.is_displayed() for e in error_element):
                logger.error("❌ Login falhou: Mensagem 'Usuário ou senha inválido' detectada.")
                self.voice_manager.speak("Falha no login. Usuário ou senha incorretos.")
                self._update_status("Erro: Credenciais Inválidas")
                # Não retornamos False aqui para permitir que o loop de tentativa/erro principal trate?
                # Não, isso é um erro fatal de configuração, não transiente. Devemos parar.
                self.stop() # Força parada total
                return False
        except Exception:
            pass # Continua se der erro na verificação

        # Após o login, verificar e fechar o popup de Comunicação Interna
        # Este passo é opcional e não deve falhar a automação se o popup não aparecer.
        logger.info("   Verificando possível popup de 'Comunicação Interna'...")
        close_button = validar_e_localizar_elemento(self.driver, By.XPATH, "//span[contains(text(), 'Comunicação Interna')]/following-sibling::button", timeout=10)
        if close_button:
            logger.info("   Janela de 'Comunicação Interna' encontrada. Fechando...")
            safe_click(self.driver, close_button)
            aguardar_invisibilidade(self.driver, By.XPATH, "//span[contains(text(), 'Comunicação Interna')]")
        else:
            logger.info("   Janela de 'Comunicação Interna' não apareceu. Continuando.")

        # Validação final: o campo de busca da página principal deve aparecer
        logger.info("   Validando sucesso do login pela presença do campo de busca...")
        search_field_next_page = validar_e_localizar_elemento(self.driver, By.CSS_SELECTOR, "input.w-launcher__search", timeout=20)
        if not search_field_next_page:
            logger.error("Login parece ter falhado. O campo de busca da página principal não foi encontrado após tratar popups.")
            return False
        
        self._update_status("Login realizado")
        return True

    def _step_buscar_gerenciamento_senhas(self) -> bool:
        logger.info(f"🤖 [{self.automation_type}] PASSO 4/5: Navegando para 'Gerenciamento de Senhas'...")
        search_field = validar_e_localizar_elemento(self.driver, By.CSS_SELECTOR, "input.w-launcher__search")
        if not search_field: return False
        safe_send_keys(search_field, "Gerenciamento de Senhas")

        result_item = validar_e_localizar_elemento(self.driver, By.XPATH, "//*[contains(text(), 'Gerenciamento de Senhas')]")
        if not result_item: return False
        safe_click(self.driver, result_item)

        # Validação de sucesso: o dropdown da próxima tela deve aparecer
        dropdown_next_page = validar_e_localizar_elemento(self.driver, By.CSS_SELECTOR, "div.w-listbox__label", timeout=20)
        if not dropdown_next_page: 
            logger.error("Navegação para 'Gerenciamento de Senhas' falhou. A tela seguinte não carregou.")
            return False

        self._update_status("Navegou para Gerenciamento de Senhas")
        return True

    def _step_select_automation_mode(self) -> bool:
        target_text = 'Monitor' if self.automation_type == 'Monitor de Senhas' else 'Senhas'
        logger.info(f"🤖 [{self.automation_type}] PASSO 5/5: Selecionando modo '{target_text}'...")
        self._update_status(f"Selecionando modo: {target_text}")

        # Loop principal de tentativas para todo o processo de seleção
        for attempt in range(1, 4):
            logger.info(f"   Tentativa {attempt}/3 para selecionar o modo '{target_text}'.")
            self._update_status(f"Tentativa {attempt}/3: Selecionar {target_text}")
            
            try:
                # 1. Localiza o dropdown e verifica se a troca é necessária
                dropdown = validar_e_localizar_elemento(self.driver, By.CSS_SELECTOR, "div.w-listbox__label", timeout=25)
                if not dropdown:
                    logger.error("   Dropdown para seleção de modo não foi encontrado. A automação será interrompida.")
                    return False # Erro fatal, não adianta tentar de novo

                if target_text in dropdown.text:
                    logger.info(f"   '{target_text}' já está selecionado.")
                    self._update_status(f"Modo {target_text} já selecionado")
                    return True

                # 2. Tenta abrir o dropdown
                logger.info("   Abrindo o dropdown...")
                safe_click(self.driver, dropdown)
                
                # Validação: O container das opções ficou visível?
                WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "div.w-listbox__content"))
                )
                logger.info("   Dropdown aberto com sucesso.")

                # 3. Com o dropdown aberto, seleciona a opção
                logger.info("   Aguardando máscara de loading (se houver) desaparecer...")
                aguardar_invisibilidade(self.driver, By.CSS_SELECTOR, "div.w-loader.w-loader--spinner", timeout=45)

                logger.info(f"   Clicando na opção '{target_text}'...")
                option_xpath = f"//a[.//span[normalize-space()='{target_text}']]"
                option = validar_e_localizar_elemento(self.driver, By.XPATH, option_xpath)
                
                if not option:
                    # Se a opção não foi encontrada, o dropdown pode ter fechado.
                    # Lança uma exceção para forçar uma nova tentativa completa.
                    raise TimeoutException(f"Opção '{target_text}' não encontrada na lista.")
                
                safe_click(self.driver, option)

                # 4. Valida se a seleção foi bem-sucedida
                # A validação mais robusta é esperar o texto do próprio dropdown mudar.
                logger.info("   Aguardando confirmação da mudança de modo...")
                self._update_status("Aguardando confirmação...")
                WebDriverWait(self.driver, 15).until(
                    EC.text_to_be_present_in_element((By.CSS_SELECTOR, "div.w-listbox__label"), target_text)
                )
                
                logger.info(f"✅ Modo '{target_text}' selecionado com sucesso.")
                return True # Sucesso, sai da função

            except StaleElementReferenceException:
                logger.warning(f"   Elemento ficou obsoleto durante a tentativa {attempt}. Tentando novamente...")
                self._update_status(f"Retry {attempt}: Elemento obsoleto")
            except Exception as e:
                logger.warning(f"   Falha na tentativa {attempt}: {type(e).__name__}. Tentando novamente...")
                self._update_status(f"Retry {attempt}: {type(e).__name__}")
            
            # Pausa antes da próxima tentativa
            if attempt < 3:
                time.sleep(2)

        logger.error(f"❌ Falha ao selecionar o modo '{target_text}' após 3 tentativas.")
        return False

    def _is_healthy(self) -> bool:
        """
        Verifica a saúde da automação com a máxima robustez, usando uma hierarquia de múltiplos critérios.
        """
        if not self.driver:
            return False
        
        try:
            # --- VERIFICAÇÃO DE CONDIÇÕES DE ERRO CONHECIDAS ---

            # CRITÉRIO 1: Diálogo de erro específico do Tasy está visível?
            try:
                tasy_error_dialog_xpath = "//div[contains(@class, 'dialog-text') and contains(text(), 'Não foi possível conectar-se com o servidor')]"
                error_dialog = self.driver.find_element(By.XPATH, tasy_error_dialog_xpath)
                if error_dialog.is_displayed():
                    logger.error(f"🩺 [{self.automation_type}] Problema de saúde confirmado: Diálogo de erro do Tasy encontrado.")
                    return False
            except Exception:
                pass # Elemento não encontrado, o que é bom, continuamos a verificação.

            # CRITÉRIO 2: A página é uma página de erro genérica do navegador?
            page_source = self.driver.page_source
            generic_error_strings = [
                "Esta página da Web não está disponível",
                "Hmmm... não é possível acessar esta página"
            ]
            for error in generic_error_strings:
                if error in page_source:
                    logger.error(f"🩺 [{self.automation_type}] Problema de saúde confirmado: Página de erro do navegador encontrada ('{error}').")
                    return False

            # --- VERIFICAÇÃO DA CONDIÇÃO DE SUCESSO ---

            # CRITÉRIO 3: Se nenhuma condição de erro foi encontrada, o elemento principal da aplicação está lá?
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.w-listbox__label"))
            )
            
            # Se chegou até aqui, está tudo saudável.
            return True

        except Exception as e:
            # Se qualquer uma das verificações acima falhou de forma inesperada (e.g. a sessão do driver morreu no meio),
            # ou se o CRITÉRIO 3 falhou (TimeoutException), caímos aqui.
            # Isso representa uma falha de saúde definitiva.
            logger.error(f"🩺 [{self.automation_type}] Problema de saúde detectado. A automação não está em um estado válido. Erro: {type(e).__name__}")
            return False
