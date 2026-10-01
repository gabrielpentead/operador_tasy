# Painel de Senhas HSV - Sistema de Gerenciamento de Operadores

## 🏥 Visão Geral

O **Painel de Senhas HSV** é um sistema completo e moderno para gerenciamento centralizado de operadores do sistema de chamado de senhas Tasy no Hospital São Vicente. A solução utiliza uma arquitetura cliente-servidor robusta, permitindo o controle remoto de múltiplos terminais de chamado de senhas distribuídos pelo hospital.

Este projeto foi totalmente refatorado para uma arquitetura modular, garantindo maior manutenibilidade, estabilidade e facilidade para futuras expansões.

## 🏗️ Arquitetura do Sistema

### 🖥️ Servidor Central (`/server`)
- **Backend**: Flask (Python) com arquitetura modular.
- **Comunicação**: API REST para gerenciamento e Socket.IO para comunicação em tempo real com os clientes.
- **Banco de Dados**: SQLite para armazenamento de operadores e configurações.
- **Interface**: Dashboard web responsivo para monitoramento e controle dos operadores.

### 💻 Cliente Operador (`/operador`)
- **Aplicação Desktop**: Python com arquitetura modular, projetado para rodar em terminais Windows.
- **Automação**: Selenium para controlar uma instância do Microsoft Edge em modo Kiosk.
- **Comunicação**: Cliente Socket.IO para conexão persistente com o servidor, permitindo o recebimento de comandos em tempo real.
- **Distribuição**: Empacotado em um executável `.exe` standalone usando PyInstaller.

## ✨ Funcionalidades Principais

### Servidor
- **Dashboard Centralizado**: Visualize o status (Online, Offline, Executando, etc.) de todos os operadores em tempo real.
- **Controle Remoto**: Envie comandos de `iniciar`, `parar` e `reiniciar` para qualquer operador conectado.
- **Gerenciamento de Operadores**: Adicione, edite e remova operadores e suas credenciais do Tasy de forma segura.
- **Configuração Centralizada**: Atualize as credenciais de um operador e envie-as para o cliente remotamente.

### Cliente
- **Automação Robusta**: Executa a sequência de login e configuração do monitor de senhas no Tasy de forma autônoma.
- **Auto-registro**: Na primeira execução em um novo terminal, um guia interativo solicita as informações para registrar o operador no servidor.
- **Operação Offline-Ready**: O cliente pode funcionar em redes restritas se o `msedgedriver.exe` for fornecido localmente.
- **Síntese de Voz**: Utiliza as vozes neurais do Microsoft Edge para anúncios.
- **Resiliência**: Tenta se reconectar ao servidor em caso de queda de conexão e possui um mecanismo de recuperação em caso de falha na automação.

## 📁 Estrutura do Projeto (Atualizada)

```
painel-senhas-automacao/
├── operador/                  # 💻 CLIENTE OPERADOR (MODULAR)
│   ├── automation/            # 🤖 Módulos de automação com Selenium
│   ├── communication/         # 📡 Módulos de comunicação (WebSocket, API)
│   ├── core/                  # 🎯 Lógica principal do cliente e configuração
│   ├── utils/                 # 🛠️ Constantes e funções utilitárias
│   ├── app.ico
│   ├── build_modular.py       # 🔨 Script para compilar o executável do cliente
│   └── tasy_operador_modular.py # 🚀 Entry point do cliente
│
└── server/                    # 🖥️ SERVIDOR CENTRAL
    ├── core/                  # 🎯 Módulos centrais
    │   ├── app.py             #    Fábrica da aplicação Flask + SocketIO
    │   ├── config.py          #    Configuração (arquivo + variáveis de ambiente)
    │   ├── auth.py            #    Autenticação, sessão e usuários
    │   ├── database.py        #    Acesso ao banco (SQLite) e migrações
    │   └── email_service.py   #    Envio de e-mail (SMTP)
    ├── routes/                # 🌐 Rotas: api, auth_api, alertas_api, health_api, views, websocket
    ├── monitoring/            # 🚨 Detecção de incidentes e alertas por e-mail
    │   ├── incident_detector.py  # correlação por unidade (pelos painéis)
    │   ├── tasy_host_monitor.py  # disponibilidade do host do Tasy
    │   ├── alert_mailer.py       # montagem/envio dos alertas
    │   └── incident_store.py     # trilha de auditoria dos incidentes
    ├── frontend/              # ⚛️ App React (Vite) — código-fonte da interface
    ├── static/app/            # 📦 Build do frontend servido em produção (npm run build)
    ├── static/                # 🎨 CSS/JS/imagens (style.css, logo)
    ├── utils/                 # 🛠️ Utilitários do servidor (logging)
    ├── data/                  # 🔒 Banco e server_config.json (NÃO versionado)
    ├── .env.example           # 📝 Referência de todas as variáveis de ambiente
    ├── requirements.txt       # Dependências Python do servidor
    ├── run.py                 # 🚀 Entry point do servidor
    └── testar_local.py        # 🧪 Sobe o servidor com SMTP de captura (dev)
```

## 🚀 Guia de Instalação e Execução

### 🖥️ Servidor Central

**Pré-requisitos:**
- Python 3.8+

**Passos:**
1.  Navegue até o diretório do servidor:
    ```bash
    cd server
    ```
2.  Crie um ambiente virtual e ative-o:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  (Opcional) Configure o servidor. A maioria dos parâmetros vem de
    `data/server_config.json`; segredos e ajustes finos podem vir de variáveis
    de ambiente. Veja **`.env.example`** para a lista completa (SMTP, monitor do
    Tasy, alertas). Segredos como `TASY_SMTP_SENHA` devem ficar só no ambiente
    (ex.: `setx TASY_SMTP_SENHA "..."`), nunca em arquivo versionado.
5.  Execute o servidor:
    ```bash
    python run.py
    ```
    O servidor estará acessível em `http://<seu-ip-local>:5000` e a interface em `/app`.

**Interface (React):** o código-fonte fica em `server/frontend/`. Para gerar a
versão servida em produção (`server/static/app/`):
```bash
cd server/frontend
npm install
npm run build
```
No deploy, leve também o `server/static/app/` gerado. **Nunca copie `server/data/`**
(contém o banco e as credenciais reais).

### 💻 Cliente Operador

**1. Compilando o Executável:**

O cliente foi projetado para ser distribuído como um único arquivo `.exe`.

**Pré-requisitos:**
- Python 3.8+ (para o ambiente de compilação)
- Microsoft Windows

**Passos:**
1.  Navegue até o diretório do operador:
    ```bash
    cd operador
    ```
2.  (Opcional) Crie e ative um ambiente virtual e instale as dependências do `build_modular.py` (pyinstaller, etc.).
3.  Execute o script de build:
    ```bash
    python build_modular.py
    ```
4.  Após a conclusão, o executável `Tasy_Operador_Modular.exe` estará localizado na pasta `operador/dist/`.

**2. Executando o Cliente:**

1.  Copie o arquivo `Tasy_Operador_Modular.exe` da pasta `dist` para o terminal desejado.
2.  **Para ambientes offline/restritos:** Baixe a versão correta do **Microsoft Edge Driver** ([link oficial](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/)) e coloque o arquivo `msedgedriver.exe` na mesma pasta que o `Tasy_Operador_Modular.exe`.
3.  Execute `Tasy_Operador_Modular.exe`.
4.  Na primeira vez, siga as instruções no console para registrar o terminal no servidor. As credenciais fornecidas serão salvas localmente em um arquivo `config.ini`.
5.  Após o registro, o cliente se conectará ao servidor e aguardará o comando para iniciar a automação.

## 🔧 Solução de Problemas

### Cliente não inicia a automação (Erro de WebDriver)
- **Causa:** O cliente não consegue encontrar ou baixar o `msedgedriver.exe`.
- **Solução:** Baixe o driver manualmente do [site oficial da Microsoft](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/), garantindo que a versão do driver corresponda à versão do Microsoft Edge instalado no terminal. Coloque o arquivo `msedgedriver.exe` na mesma pasta do `Tasy_Operador_Modular.exe`.

### Cliente não conecta ao servidor
- **Causa:** O endereço do servidor no `config.ini` do cliente está incorreto ou há um problema de rede.
- **Solução:**
    1.  Verifique se o terminal do cliente consegue acessar o IP e a porta do servidor (use o comando `ping <ip-do-servidor>`).
    2.  Abra o arquivo `config.ini` (localizado na mesma pasta do `.exe`) e verifique se o `host` e a `porta` na seção `[servidor]` estão corretos.

### Banco de Dados (Servidor)
- As migrações de esquema são **automáticas**: ao iniciar, `core/database.py` verifica
  as tabelas/colunas e aplica o que faltar (`_verificar_migracao`), sem script manual.
- Em caso de banco corrompido, restaure a partir de um backup em `data/` e reinicie o servidor.
    Após a migração, reinicie o servidor.