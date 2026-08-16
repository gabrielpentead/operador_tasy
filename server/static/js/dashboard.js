/**
 * dashboard.js - Lógica da interface para o painel de operadores.
 */

// A variável 'dadosOperadores' é declarada em common.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard inicializado.');
    carregarOperadores();
    configurarEventosWebSocket();

    document.getElementById('filtro-operador').addEventListener('input', filtrarOperadores);
    document.getElementById('btnSalvarOperador').addEventListener('click', () => salvarOperador(false));
    document.getElementById('btnAtualizarOperador').addEventListener('click', () => salvarOperador(true));
    
    // Configuração do Modal de Senha Admin
    const btnConfirmarAdmin = document.getElementById('btnConfirmarSenhaAdmin');
    const inputSenhaAdmin = document.getElementById('admin-password-input');
    
    if (btnConfirmarAdmin) {
        btnConfirmarAdmin.addEventListener('click', verificarSenhaAdmin);
    }
    
    if (inputSenhaAdmin) {
        inputSenhaAdmin.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') verificarSenhaAdmin();
        });
        inputSenhaAdmin.addEventListener('input', () => {
            const erroEl = document.getElementById('admin-password-error');
            if (erroEl) erroEl.classList.add('d-none');
        });
        
        // Focar no input quando o modal abrir
        const modalAdminEl = document.getElementById('modalSenhaAdmin');
        if (modalAdminEl) {
            modalAdminEl.addEventListener('shown.bs.modal', () => {
                inputSenhaAdmin.focus();
            });
        }
    }

    const modalEditar = document.getElementById('modalEditarOperador');
    if(modalEditar) {
        document.getElementById('edit-tipo_cadastro').addEventListener('change', toggleCredentialFields);
        document.getElementById('edit-usa_credenciais_separadas').addEventListener('change', toggleCredentialFields);
    }
});

function isPartRunning(status) {
    if (typeof status !== 'string' || !status) {
        return false;
    }
    const lowerStatus = status.toLowerCase();
    // A automação está rodando se o status NÃO for um dos estados de parada explícitos.
    const stoppedStates = ['parado', 'erro', 'desconectado', 'inicializado'];
    return !stoppedStates.some(s => lowerStatus.includes(s));
}

function getAutomationStatus(operador) {
    const status = {
        monitor: { isRunning: false, text: 'Parado' },
        totem: { isRunning: false, text: 'Parado' }
    };

    if (!operador || !operador.online || !operador.status) {
        return status;
    }

    const opStatus = operador.status;

    if (operador.tipo_cadastro === 'Monitor de Senhas') {
        const statusText = (typeof opStatus === 'object' && opStatus !== null) ? opStatus.monitor : opStatus;
        status.monitor.text = statusText || 'Parado';
        status.monitor.isRunning = isPartRunning(status.monitor.text);
    } else if (operador.tipo_cadastro === 'Totem de Senhas') {
        const statusText = (typeof opStatus === 'object' && opStatus !== null) ? opStatus.totem : opStatus;
        status.totem.text = statusText || 'Parado';
        status.totem.isRunning = isPartRunning(status.totem.text);
    } else if (operador.tipo_cadastro === 'Ambos') {
        if (typeof opStatus === 'object' && opStatus !== null) {
            status.monitor.text = opStatus.monitor || 'Parado';
            status.monitor.isRunning = isPartRunning(status.monitor.text);
            status.totem.text = opStatus.totem || 'Parado';
            status.totem.isRunning = isPartRunning(status.totem.text);
        } else { // Fallback if status is a single string for "Ambos" type
            const statusText = typeof opStatus === 'string' ? opStatus : 'Indefinido';
            const isRunning = isPartRunning(statusText);
            status.monitor.text = statusText;
            status.monitor.isRunning = isRunning;
            status.totem.text = statusText;
            status.totem.isRunning = isRunning;
        }
    }
    return status;
}

function criarStatusDetailsHTML(operador) {
    if (!operador || !operador.online || !operador.status) {
        return '<div class="text-center text-muted p-2"><i>Status indisponível</i></div>';
    }

    const automationStatus = getAutomationStatus(operador);

    if (operador.tipo_cadastro === 'Ambos') {
        return Object.entries(automationStatus).map(([key, partStatus]) => {
            const { isRunning, text } = partStatus;
            const isError = String(text).toLowerCase().includes('erro');
            const icon = isError ? 'bi-exclamation-triangle-fill text-danger' : (isRunning ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-muted');
            return `<div class="info-item"><span class="info-label text-capitalize">${key}</span><span class="info-value"><i class="bi ${icon} me-1"></i>${escapeHtml(text)}</span></div>`;
        }).join('');
    } else {
        const partKey = (operador.tipo_cadastro === 'Monitor de Senhas') ? 'monitor' : 'totem';
        const { isRunning, text } = automationStatus[partKey];
        const isError = String(text).toLowerCase().includes('erro');
        const icon = isError ? 'bi-exclamation-triangle-fill text-danger' : (isRunning ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-muted');
        return `<div class="info-item"><span class="info-label">Status</span><span class="info-value"><i class="bi ${icon} me-1"></i>${escapeHtml(text)}</span></div>`;
    }
}

function toggleCredentialFields() {
    const tipoCadastro = document.getElementById('edit-tipo_cadastro').value;
    const usaSeparadas = document.getElementById('edit-usa_credenciais_separadas').checked;
    
    const credenciaisSection = document.getElementById('credenciais-section');
    const sharedCredentials = document.getElementById('shared-credentials');
    const separateCredentials = document.getElementById('separate-credentials');

    if (!credenciaisSection || !sharedCredentials || !separateCredentials) return;

    if (tipoCadastro === 'Ambos') {
        credenciaisSection.style.display = 'block';
        if (usaSeparadas) {
            sharedCredentials.style.display = 'none';
            separateCredentials.style.display = 'block';
        } else {
            sharedCredentials.style.display = 'block';
            separateCredentials.style.display = 'none';
        }
    } else {
        credenciaisSection.style.display = 'block';
        sharedCredentials.style.display = 'block';
        separateCredentials.style.display = 'none';
        document.getElementById('edit-usa_credenciais_separadas').checked = false;
    }
}

function configurarEventosWebSocket() {
    if (!socket) {
        console.warn('Socket.IO não inicializado. Eventos de WebSocket não serão configurados.');
        return;
    }
    socket.on('status_operador', data => {
        if (data && data.id) {
            atualizarOperadorNaTela(data.id, data);
        }
    });
    socket.on('operador_adicionado', () => {
        mostrarNotificacao('Novo operador adicionado', 'success');
        carregarOperadores();
    });
    socket.on('operador_removido', () => {
        mostrarNotificacao('Operador removido', 'info');
        carregarOperadores();
    });
    socket.on('saude_atualizada', data => {
        if (data && data.id) {
            atualizarSaudeOperador(data.id, data);
        }
    });
    socket.on('comando_recebido', (data) => {
        mostrarNotificacao(`Comando '${data.comando}' recebido pelo operador.`, 'info');
    });
    socket.on('resultado_comando', (data) => {
        const tipo = data.sucesso ? 'success' : 'danger';
        const icone = data.sucesso ? '✅' : '❌';
        mostrarNotificacao(`${icone} ${data.mensagem}`, tipo);
        carregarOperadores();
    });
}

async function carregarOperadores() {
    try {
        const response = await fetch('/api/operadores');
        const data = await response.json();
        if (data.success) {
            dadosOperadores = data.operadores;
            renderizarOperadores();
            atualizarContadores();
        } else {
            mostrarNotificacao(`Erro ao carregar operadores: ${data.error}`, 'danger');
        }
    } catch (error) {
        mostrarNotificacao(`Erro de conexão ao carregar operadores: ${error.message}`, 'danger');
    }
}

function renderizarOperadores() {
    const container = document.getElementById('lista-operadores');
    const semOperadores = document.getElementById('sem-operadores');
    const carregando = document.getElementById('carregando-operadores');
    
    if (carregando) carregando.style.display = 'none';
    if (!container || !semOperadores) return;

    container.innerHTML = '';
    if (!dadosOperadores || dadosOperadores.length === 0) {
        semOperadores.style.display = 'block';
        return;
    }
    semOperadores.style.display = 'none';

    dadosOperadores.forEach(operador => {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4 mb-4 operador-item';
        col.id = `operador-item-${operador.id}`;
        col.dataset.nome = operador.nome.toLowerCase();
        col.dataset.descricao = (operador.descricao || '').toLowerCase();
        col.innerHTML = criarCartaoOperador(operador);
        container.appendChild(col);
    });
    filtrarOperadores();
}

function criarCartaoOperador(operador) {
    const isOnline = operador.online;
    const statusBadge = isOnline 
        ? `<span class="badge bg-success-soft text-success"><i class="bi bi-check-circle-fill"></i> Online</span>` 
        : `<span class="badge bg-danger-soft text-danger"><i class="bi bi-x-circle-fill"></i> Offline</span>`;

    let cardTypeClass = '';
    let typeIconHTML = '';
    const iconClass = 'type-icon-img';
    if (operador.tipo_cadastro === 'Monitor de Senhas') {
        cardTypeClass = 'tipo-monitor';
        typeIconHTML = `<img src="/static/img/monitor.png" class="${iconClass}" title="Monitor de Senhas">`;
    } else if (operador.tipo_cadastro === 'Totem de Senhas') {
        cardTypeClass = 'tipo-totem';
        typeIconHTML = `<img src="/static/img/totem.png" class="${iconClass}" title="Totem de Senhas">`;
    } else if (operador.tipo_cadastro === 'Ambos') {
        cardTypeClass = 'tipo-ambos';
        typeIconHTML = `<img src="/static/img/monitor.png" class="${iconClass}" title="Monitor"> &nbsp; <img src="/static/img/totem.png" class="${iconClass}" title="Totem">`;
    }

    const automationStatus = getAutomationStatus(operador);
    const isAnyRunning = automationStatus.monitor.isRunning || automationStatus.totem.isRunning;

    let statusGeralBadge = '';
    if (isOnline) {
        statusGeralBadge = isAnyRunning
            ? `<span class="badge bg-info-soft text-info">Iniciado</span>`
            : `<span class="badge bg-warning-soft text-warning">Parado</span>`;
    }

    const statusDetailsHTML = criarStatusDetailsHTML(operador);

    const botoesHTML = `
        <div class="btn-group w-100 action-buttons" role="group">
            <button class="btn btn-action-control btn-iniciar ${isAnyRunning ? 'no-hover-effect' : ''}" onclick="prepararComando('${operador.id}', 'iniciar')" title="Iniciar" ${!isOnline ? 'disabled' : ''}><i class="bi bi-play-fill"></i></button>
            <button class="btn btn-action-control btn-parar ${!isAnyRunning ? 'no-hover-effect' : ''}" onclick="prepararComando('${operador.id}', 'parar')" title="Parar" ${!isOnline ? 'disabled' : ''}><i class="bi bi-stop-fill"></i></button>
            <button class="btn btn-action-control btn-reiniciar" onclick="prepararComando('${operador.id}', 'reiniciar')" title="Reiniciar" ${!isOnline ? 'disabled' : ''}><i class="bi bi-arrow-clockwise"></i></button>
            <div class="btn-group" role="group">
                <button type="button" class="btn btn-action-control btn-config dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false" title="Mais opções">
                    <i class="bi bi-gear-fill"></i>
                </button>
                <ul class="dropdown-menu dropdown-menu-end">
                    <li><a class="dropdown-item" href="#" onclick="abrirModalEdicao('${operador.id}')"><i class="bi bi-pencil-fill"></i> Editar Operador</a></li>
                    <li><a class="dropdown-item text-danger" href="#" onclick="confirmarExclusao('${operador.id}', '${escapeHtml(operador.nome)}')"><i class="bi bi-trash-fill"></i> Excluir Operador</a></li>
                </ul>
            </div>
        </div>`;

    return `
        <div class="operador-card-repaginado ${cardTypeClass}">
            <div class="card-body">
                <div class="operador-header">
                    <div class="operador-nome">${escapeHtml(operador.nome)}</div>
                    <div class="operador-status-badge">${statusBadge}</div>
                </div>
                <div class="operador-info">
                    <div class="info-item">
                        <span class="info-label">Hostname</span>
                        <span class="info-value font-monospace">${escapeHtml(operador.hostname || 'N/A')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Tipo</span>
                        <span class="info-value">${typeIconHTML}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Usuário Tasy</span>
                        <span class="info-value font-monospace">${escapeHtml(operador.username || 'N/A')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Senha</span>
                        <div class="d-flex align-items-center justify-content-end" style="min-width: 0; flex: 1; margin-left: 10px;">
                            <span class="info-value font-monospace text-truncate" id="senha-texto-${operador.id}" style="margin-right: 8px;">********</span>
                            <button class="btn btn-link btn-sm text-muted p-0 border-0 text-decoration-none" type="button" onclick="revelarSenha('${operador.id}', '${escapeHtml(operador.password || '')}')" title="Revelar/Ocultar senha" style="line-height: 1;">
                                <i class="bi bi-eye-slash-fill" id="icon-senha-${operador.id}"></i>
                            </button>
                        </div>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Endereço IP</span>
                        <span class="info-value font-monospace">${escapeHtml(operador.ip || 'N/A')}</span>
                    </div>
                </div>
                <div class="automation-status">
                    <h6 class="automation-status-title">Status da Automação ${statusGeralBadge}</h6>
                    <div id="status-details-${operador.id}">
                        ${statusDetailsHTML}
                    </div>
                </div>
                <div class="operador-health-section" id="health-section-${operador.id}">
                    ${criarHealthMiniHTML(operador.saude, operador.nivel_saude)}
                </div>
                <div class="action-section mt-auto" id="action-buttons-${operador.id}">
                    ${botoesHTML}
                </div>
            </div>
        </div>`;
}

function atualizarOperadorNaTela(operadorId, data) {
    const index = dadosOperadores.findIndex(op => op.id === operadorId);
    if (index === -1) return;

    Object.assign(dadosOperadores[index], data);
    const operador = dadosOperadores[index];

    const card = document.getElementById(`operador-item-${operador.id}`);
    if (!card) return;

    // Atualiza o badge de status no cabeçalho do card
    const statusBadgeEl = card.querySelector(`.operador-status-badge`);
    if (statusBadgeEl) {
        statusBadgeEl.innerHTML = operador.online 
            ? `<span class="badge bg-success-soft text-success"><i class="bi bi-check-circle-fill"></i> Online</span>` 
            : `<span class="badge bg-danger-soft text-danger"><i class="bi bi-x-circle-fill"></i> Offline</span>`;
    }

    const automationStatus = getAutomationStatus(operador);
    const isAnyRunning = automationStatus.monitor.isRunning || automationStatus.totem.isRunning;

    let statusGeralBadge = '';
    if (operador.online) {
        statusGeralBadge = isAnyRunning
            ? `<span class="badge bg-info-soft text-info">Iniciado</span>`
            : `<span class="badge bg-warning-soft text-warning">Parado</span>`;
    }

    const statusTitleEl = card.querySelector('.automation-status-title');
    if(statusTitleEl) {
        statusTitleEl.innerHTML = `Status da Automação ${statusGeralBadge}`;
    }

    // Atualiza os detalhes da automação
    const statusDetailsEl = card.querySelector(`#status-details-${operador.id}`);
    if (statusDetailsEl) {
        statusDetailsEl.innerHTML = criarStatusDetailsHTML(operador);
    }

    // Atualiza o estado dos botões de ação
    const actionButtonsEl = card.querySelector(`#action-buttons-${operador.id}`);
    if (actionButtonsEl) {
        const commandItems = actionButtonsEl.querySelectorAll('button');
        commandItems.forEach(item => {
            item.disabled = !operador.online;
        });

        const btnIniciar = actionButtonsEl.querySelector('.btn-iniciar');
        const btnParar = actionButtonsEl.querySelector('.btn-parar');
        if(btnIniciar) {
            isAnyRunning ? btnIniciar.classList.add('no-hover-effect') : btnIniciar.classList.remove('no-hover-effect');
        }
        if(btnParar) {
            !isAnyRunning ? btnParar.classList.add('no-hover-effect') : btnParar.classList.remove('no-hover-effect');
        }
    }

    // Atualiza seção de saúde se vieram dados
    if (data.saude !== undefined || data.nivel_saude !== undefined) {
        const healthEl = card.querySelector(`#health-section-${operador.id}`);
        if (healthEl) {
            healthEl.innerHTML = criarHealthMiniHTML(operador.saude, operador.nivel_saude);
        }
    }

    atualizarContadores();
}

// Variáveis globais para controle do modal de senha
let currentPasswordRevealId = null;
let currentPasswordRevealReal = null;

function verificarSenhaAdmin() {
    const inputSenha = document.getElementById('admin-password-input');
    const erroEl = document.getElementById('admin-password-error');
    const modalEl = document.getElementById('modalSenhaAdmin');
    
    if (!inputSenha) return;
    
    const adminPass = inputSenha.value;
    
    if (adminPass === "n3t2i1") {
        if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
        mostrarSenha(currentPasswordRevealId, currentPasswordRevealReal);
        inputSenha.value = ''; // Limpar
        if (erroEl) erroEl.classList.add('d-none');
    } else {
        if (erroEl) erroEl.classList.remove('d-none');
        inputSenha.value = '';
        inputSenha.focus();
    }
}

function mostrarSenha(id, senhaReal) {
    const spanSenha = document.getElementById(`senha-texto-${id}`);
    const iconSenha = document.getElementById(`icon-senha-${id}`);
    
    if (spanSenha && iconSenha) {
        spanSenha.textContent = senhaReal;
        iconSenha.className = 'bi bi-eye-fill text-primary';
        spanSenha.classList.add('text-primary'); // Destaque visual
    }
}

function revelarSenha(id, senhaReal) {
    const spanSenha = document.getElementById(`senha-texto-${id}`);
    const iconSenha = document.getElementById(`icon-senha-${id}`);
    
    if (!spanSenha || !iconSenha) return;
    
    const isHidden = spanSenha.textContent === '********';
    
    if (isHidden) {
        // Preparar e abrir modal
        currentPasswordRevealId = id;
        currentPasswordRevealReal = senhaReal;
        
        const modalEl = document.getElementById('modalSenhaAdmin');
        const inputSenha = document.getElementById('admin-password-input');
        const erroEl = document.getElementById('admin-password-error');
        
        if (inputSenha) inputSenha.value = '';
        if (erroEl) erroEl.classList.add('d-none');
        
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } else {
            // Fallback caso modal não exista
            const adminPass = prompt("Digite a senha de administrador para visualizar:");
            if (adminPass === "n3t2i1") {
                mostrarSenha(id, senhaReal);
            } else if (adminPass !== null) {
                alert("Senha incorreta!");
            }
        }
    } else {
        // Ocultar senha manualmente
        spanSenha.textContent = '********';
        iconSenha.className = 'bi bi-eye-slash-fill';
        iconSenha.classList.remove('text-primary');
        spanSenha.classList.remove('text-primary');
    }
}

function atualizarContadores() {
    let totalMonitores = 0, onlineMonitores = 0, iniciadosMonitores = 0;
    let totalTotens = 0, onlineTotens = 0, iniciadosTotens = 0;

    dadosOperadores.forEach(op => {
        const automationStatus = getAutomationStatus(op);
        const isMonitorType = op.tipo_cadastro === 'Monitor de Senhas' || op.tipo_cadastro === 'Ambos';
        const isTotemType = op.tipo_cadastro === 'Totem de Senhas' || op.tipo_cadastro === 'Ambos';

        if (isMonitorType) {
            totalMonitores++;
            if (op.online) {
                onlineMonitores++;
                if (automationStatus.monitor.isRunning) {
                    iniciadosMonitores++;
                }
            }
        }
        if (isTotemType) {
            totalTotens++;
            if (op.online) {
                onlineTotens++;
                if (automationStatus.totem.isRunning) {
                    iniciadosTotens++;
                }
            }
        }
    });

    // Atualiza o card de Monitores
    document.getElementById('monitores-cadastrados').textContent = totalMonitores;
    document.getElementById('monitores-online').textContent = onlineMonitores;
    document.getElementById('monitores-offline').textContent = totalMonitores - onlineMonitores;
    document.getElementById('monitores-iniciados').textContent = iniciadosMonitores;
    document.getElementById('monitores-parados').textContent = onlineMonitores - iniciadosMonitores;

    // Atualiza o card de Totens
    document.getElementById('totens-cadastrados').textContent = totalTotens;
    document.getElementById('totens-online').textContent = onlineTotens;
    document.getElementById('totens-offline').textContent = totalTotens - onlineTotens;
    document.getElementById('totens-iniciados').textContent = iniciadosTotens;
    document.getElementById('totens-parados').textContent = onlineTotens - iniciadosTotens;

}

function filtrarOperadores() {
    const filtro = document.getElementById('filtro-operador').value.toLowerCase();
    document.querySelectorAll('.operador-item').forEach(item => {
        const nome = item.dataset.nome || '';
        const descricao = item.dataset.descricao || '';
        item.style.display = (nome.includes(filtro) || descricao.includes(filtro)) ? '' : 'none';
    });
}

async function enviarComando(operadorId, comando, target = 'ambos') {
    try {
        const response = await fetch(`/api/operadores/${operadorId}/comando`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comando, target }) });
        const data = await response.json();
        mostrarNotificacao(data.success ? `Comando '${comando}' enviado.` : `Erro: ${data.error}`, data.success ? 'success' : 'danger');
    } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger');
    }
}

async function salvarOperador(isEdit) {
    const formPrefix = isEdit ? 'edit-' : '';
    const modalId = isEdit ? 'modalEditarOperador' : 'modalAdicionarOperador';
    const id = isEdit ? document.getElementById('edit-id').value : null;

    const tipoCadastro = document.getElementById(`${formPrefix}tipo_cadastro`).value;
    const usaCredenciaisSeparadas = document.getElementById(`${formPrefix}usa_credenciais_separadas`)?.checked || false;

    let payload = {
        nome: document.getElementById(`${formPrefix}nome`).value,
        descricao: document.getElementById(`${formPrefix}descricao`).value,
        tipo_cadastro: tipoCadastro,
        usa_credenciais_separadas: false
    };

    if (tipoCadastro === 'Ambos' && usaCredenciaisSeparadas) {
        payload.usa_credenciais_separadas = true;
        payload.username_monitor = document.getElementById(`${formPrefix}username_monitor`).value;
        payload.password_monitor = document.getElementById(`${formPrefix}password_monitor`).value;
        payload.username_totem = document.getElementById(`${formPrefix}username_totem`).value;
        payload.password_totem = document.getElementById(`${formPrefix}password_totem`).value;

        // Preenche as credenciais principais com as do monitor como fallback
        payload.username = payload.username_monitor;
        payload.password = payload.password_monitor;
    } else {
        payload.username = document.getElementById(`${formPrefix}username`).value;
        payload.password = document.getElementById(`${formPrefix}password`).value;
    }

    // Validação básica
    if (!payload.nome) {
        return mostrarNotificacao('O nome do operador é obrigatório.', 'danger');
    }

    const url = isEdit ? `/api/operadores/${id}` : '/api/operadores';
    const method = isEdit ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await response.json();
        if (data.success) {
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById(modalId));
            if (modalInstance) modalInstance.hide();
            mostrarNotificacao(`Operador ${isEdit ? 'atualizado' : 'adicionado'}.`, 'success');
            carregarOperadores();
        } else {
            mostrarNotificacao(`Erro: ${data.error}`, 'danger');
        }
    } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger');
    }
}

async function abrirModalEdicao(operadorId) {
    try {
        const response = await fetch(`/api/operadores/${operadorId}`);
        const data = await response.json();
        if (data.success) {
            const op = data.operador;
            document.getElementById('edit-id').value = op.id;
            document.getElementById('edit-nome').value = op.nome;
            document.getElementById('edit-descricao').value = op.descricao || '';
            document.getElementById('edit-tipo_cadastro').value = op.tipo_cadastro || 'Monitor de Senhas';
            
            // Preencher credenciais compartilhadas
            document.getElementById('edit-username').value = op.username || '';
            document.getElementById('edit-password').value = op.password || '';

            // Preencher credenciais do Monitor
            document.getElementById('edit-username_monitor').value = op.username_monitor || '';
            document.getElementById('edit-password_monitor').value = op.password_monitor || '';

            // Preencher credenciais do Totem
            document.getElementById('edit-username_totem').value = op.username_totem || '';
            document.getElementById('edit-password_totem').value = op.password_totem || '';

            // Marcar o checkbox
            document.getElementById('edit-usa_credenciais_separadas').checked = op.usa_credenciais_separadas || false;

            // Ajustar visibilidade dos campos
            toggleCredentialFields();

            new bootstrap.Modal(document.getElementById('modalEditarOperador')).show();
        } else {
            mostrarNotificacao(`Erro ao carregar operador: ${data.error}`, 'danger');
        }
    } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger');
    }
}

function confirmarExclusao(operadorId, nome) {
    const modalEl = document.getElementById('modalConfirmarExclusao');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);
    document.getElementById('nome-operador-exclusao').textContent = nome;
    document.getElementById('btnConfirmarExclusao').onclick = async () => {
        try {
            const response = await fetch(`/api/operadores/${operadorId}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) {
                modal.hide();
                mostrarNotificacao('Operador excluído', 'success');
                carregarOperadores();
            } else {
                mostrarNotificacao(`Erro ao excluir: ${data.error}`, 'danger');
            }
        } catch (error) {
            mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger');
        }
    };
    modal.show();
}



function prepararComando(operadorId, comando) {
    const operador = dadosOperadores.find(op => op.id === operadorId);
    if (!operador) {
        mostrarNotificacao('Operador não encontrado.', 'danger');
        return;
    }

    if (operador.tipo_cadastro === 'Ambos') {
        const modalEl = document.getElementById('modalConfirmarAcao');
        const modal = new bootstrap.Modal(modalEl);
        
        document.getElementById('nome-operador-acao').textContent = operador.nome;
        document.getElementById('modalAcaoTitulo').innerHTML = `<i class="bi bi-question-circle"></i> Confirmar Ação: ${comando.charAt(0).toUpperCase() + comando.slice(1)}`;

        const automationStatus = getAutomationStatus(operador);
        const btnMonitor = document.getElementById('btnAcaoMonitor');
        const btnTotem = document.getElementById('btnAcaoTotem');
        const btnAmbos = document.getElementById('btnAcaoAmbos');

        // Lógica para habilitar/desabilitar botões
        if (comando === 'iniciar') {
            btnMonitor.disabled = automationStatus.monitor.isRunning;
            btnTotem.disabled = automationStatus.totem.isRunning;
            btnAmbos.disabled = automationStatus.monitor.isRunning && automationStatus.totem.isRunning;
        } else if (comando === 'parar') {
            btnMonitor.disabled = !automationStatus.monitor.isRunning;
            btnTotem.disabled = !automationStatus.totem.isRunning;
            btnAmbos.disabled = !automationStatus.monitor.isRunning && !automationStatus.totem.isRunning;
        } else if (comando === 'reiniciar') {
            // Reset sempre fica disponível
            btnMonitor.disabled = false;
            btnTotem.disabled = false;
            btnAmbos.disabled = false;
        }

        btnMonitor.onclick = () => { enviarComando(operadorId, comando, 'monitor'); modal.hide(); };
        btnTotem.onclick = () => { enviarComando(operadorId, comando, 'totem'); modal.hide(); };
        btnAmbos.onclick = () => { enviarComando(operadorId, comando, 'ambos'); modal.hide(); };

        modal.show();
    } else {
        // Se não for do tipo "Ambos", envia o comando para o alvo padrão ('ambos' funciona para casos únicos)
        enviarComando(operadorId, comando, 'ambos');
    }
}

/* ============================================================
   HEALTH MONITORING — Saúde dos Operadores
   ============================================================ */

const HEALTH_THRESHOLDS = {
    atencao: { ram: 85, disco: 85, temperatura: 75 },
    critico:  { ram: 95, disco: 95, temperatura: 85 },
};

function _nivelClasse(nivel) {
    if (nivel === 'Crítico') return 'critico';
    if (nivel === 'Atenção')  return 'atencao';
    return 'normal';
}

function _nivelIcone(nivel) {
    if (nivel === 'Crítico') return 'bi-exclamation-octagon-fill';
    if (nivel === 'Atenção')  return 'bi-exclamation-triangle-fill';
    return 'bi-check-circle-fill';
}

function criarHealthMiniHTML(saude, nivel) {
    if (!saude) return '';

    const nivelBadge = nivel && nivel !== 'Normal'
        ? `<span class="badge ${nivel === 'Crítico' ? 'bg-danger-soft text-danger' : 'bg-warning-soft text-warning'}">${nivel}</span>`
        : `<span class="badge bg-success-soft text-success">Normal</span>`;

    function metricCol(label, valor, unidade, campo) {
        if (valor === null || valor === undefined) return null;
        const thr = HEALTH_THRESHOLDS;
        let colorCls = 'text-success';
        let iconCls  = 'bi-check-circle-fill text-success';
        if (campo === 'ram' || campo === 'disco') {
            if (valor >= thr.critico[campo])      { colorCls = 'text-danger';  iconCls = 'bi-exclamation-octagon-fill text-danger'; }
            else if (valor >= thr.atencao[campo]) { colorCls = 'text-warning'; iconCls = 'bi-exclamation-triangle-fill text-warning'; }
        } else if (campo === 'temperatura' && valor > 0) {
            if (valor >= thr.critico.temperatura)      { colorCls = 'text-danger';  iconCls = 'bi-exclamation-octagon-fill text-danger'; }
            else if (valor >= thr.atencao.temperatura) { colorCls = 'text-warning'; iconCls = 'bi-exclamation-triangle-fill text-warning'; }
        }
        return `<div class="op-health-col">
            <span class="op-health-label">${label}</span>
            <span class="op-health-val ${colorCls}"><i class="bi ${iconCls} me-1"></i>${Math.round(valor)}${unidade}</span>
        </div>`;
    }

    const cols = [
        metricCol('CPU',   saude.cpu_pct,   '%',  'cpu'),
        metricCol('RAM',   saude.ram_pct,   '%',  'ram'),
        metricCol('Disco', saude.disco_pct, '%',  'disco'),
    ].filter(Boolean);

    if (!cols.length) return '';

    // Intercala separadores verticais entre as colunas
    const rowHTML = cols.reduce((acc, col, i) =>
        acc + col + (i < cols.length - 1 ? '<div class="op-health-sep"></div>' : ''), '');

    return `<div class="automation-status">
        <h6 class="automation-status-title">Saúde do Sistema ${nivelBadge}</h6>
        <div class="op-health-row">${rowHTML}</div>
    </div>`;
}

function atualizarSaudeOperador(id, data) {
    const idx = dadosOperadores.findIndex(op => op.id === id);
    if (idx === -1) return;

    dadosOperadores[idx].saude       = data.saude;
    dadosOperadores[idx].nivel_saude = data.nivel;
    dadosOperadores[idx].motivos     = data.motivos || [];

    const healthEl = document.getElementById(`health-section-${id}`);
    if (healthEl) {
        healthEl.innerHTML = criarHealthMiniHTML(data.saude, data.nivel);
    }

    _notifCheckHealthChange(id, data.nivel, data.motivos);
}

function atualizarIndicadoresGerais() {
    let online = 0, atencao = 0, critico = 0;
    (dadosOperadores || []).forEach(op => {
        if (!op.online) return;
        online++;
        const n = op.nivel_saude || 'Normal';
        if (n === 'Crítico') critico++;
        else if (n === 'Atenção') atencao++;
    });

    _setIndicador('ind-online',  online);
    _setIndicador('ind-atencao', atencao);
    _setIndicador('ind-critico', critico);
}

function _setIndicador(id, valor) {
    const el = document.getElementById(id);
    if (!el) return;
    const atual = parseInt(el.textContent) || 0;
    if (atual !== valor) {
        el.textContent = valor;
        el.closest('.indicador-card')?.classList.add('indicador-pulse');
        setTimeout(() => el.closest('.indicador-card')?.classList.remove('indicador-pulse'), 600);
    }
}

function _gerarMotivosLocais(op) {
    const motivos = [];
    const saude = op.saude;
    if (!op.online) {
        motivos.push('Comunicação perdida.');
        return motivos;
    }
    if (!saude) return motivos;
    const nivel = op.nivel_saude || 'Normal';
    if (nivel === 'Normal') return motivos;
    const thr = nivel === 'Crítico' ? HEALTH_THRESHOLDS.critico : HEALTH_THRESHOLDS.atencao;
    if ((saude.ram_pct  || 0) >= thr.ram)         motivos.push(`Consumo de memória atingiu ${Math.round(saude.ram_pct)}%.`);
    if ((saude.disco_pct|| 0) >= thr.disco)        motivos.push(`Disco com ${Math.round(saude.disco_pct)}% de utilização.`);
    if (saude.temperatura > 0 && saude.temperatura >= thr.temperatura)
        motivos.push(`Temperatura do equipamento está em ${Math.round(saude.temperatura)}°C.`);
    return motivos;
}

function renderizarAlertas() {
    const container = document.getElementById('alertas-lista');
    const wrapper   = document.getElementById('central-alertas');
    const countEl   = document.getElementById('alertas-count');
    const updateEl  = document.getElementById('alertas-last-update');
    if (!container || !wrapper) return;

    const alertas = [];

    (dadosOperadores || []).forEach(op => {
        const nivel = op.nivel_saude || 'Normal';
        const isCritOffline = !op.online; // offline = alerta de comunicação perdida

        if (!op.online) {
            alertas.push({ op, nivel: 'Crítico', motivos: ['Comunicação perdida.'], icone: 'bi-wifi-off' });
            return;
        }
        if (nivel === 'Normal') return;

        const motivos = (op.motivos && op.motivos.length) ? op.motivos : _gerarMotivosLocais(op);
        if (!motivos.length) return;
        alertas.push({ op, nivel, motivos, icone: nivel === 'Crítico' ? 'bi-exclamation-octagon-fill' : 'bi-exclamation-triangle-fill' });
    });

    if (!alertas.length) {
        wrapper.classList.add('d-none');
        return;
    }

    wrapper.classList.remove('d-none');
    if (countEl) countEl.textContent = alertas.length;
    if (updateEl) {
        updateEl.textContent = 'Atualizado ' + new Date().toLocaleTimeString('pt-BR');
    }

    container.innerHTML = alertas.map(({ op, nivel, motivos, icone }) => {
        const cls   = _nivelClasse(nivel);
        const label = nivel === 'Crítico' ? 'Crítico' : 'Atenção';
        const motivoHTML = motivos.map(m => `<div class="alerta-motivo-item"><i class="bi bi-dot"></i>${escapeHtml(m)}</div>`).join('');
        return `
        <div class="alerta-item alerta-${cls}">
            <div class="alerta-icon-wrap alerta-icon-${cls}">
                <i class="bi ${icone}"></i>
            </div>
            <div class="alerta-body">
                <div class="alerta-titulo">
                    <strong>${escapeHtml(op.nome)}</strong> requer atenção
                    <span class="alerta-badge badge-alerta-${cls} ms-2">${label}</span>
                </div>
                <div class="alerta-motivos">${motivoHTML}</div>
            </div>
        </div>`;
    }).join('');
}

/* ============================================================
   CENTRAL DE NOTIFICAÇÕES
   ============================================================ */

const NOTIF_KEY  = 'hsv_notif_v1';
const NOTIF_MAX  = 20;

// Rastreamento de estado anterior para detectar TRANSIÇÕES (não emitir ao carregar)
const _notifPrev = {
    online:  {},   // operadorId → boolean
    nivel:   {},   // operadorId → string ('Normal'|'Atenção'|'Crítico')
    loaded:  false // true após o primeiro carregamento completo
};

// ── Persistência ─────────────────────────────────────────────
function _notifLoad() {
    try { return JSON.parse(localStorage.getItem(NOTIF_KEY) || '[]'); }
    catch { return []; }
}
function _notifSave(list) {
    try { localStorage.setItem(NOTIF_KEY, JSON.stringify(list.slice(0, NOTIF_MAX))); }
    catch {}
}

function _notifAdd(type, title, message, operadorId) {
    const list = _notifLoad();
    list.unshift({
        id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
        type, title, message,
        timestamp: new Date().toISOString(),
        read: false,
        operadorId: operadorId || null
    });
    _notifSave(list);
    _notifRefreshBell();
    _notifRefreshPanel();
}

// ── Bell (sino) ───────────────────────────────────────────────
function _notifRefreshBell() {
    const list   = _notifLoad();
    const unread = list.filter(n => !n.read).length;
    const badge  = document.getElementById('notif-badge');
    const btn    = document.getElementById('notif-bell-btn');
    if (badge) {
        badge.textContent = unread > 99 ? '99+' : unread;
        badge.classList.toggle('d-none', unread === 0);
    }
    if (btn) btn.classList.toggle('notif-bell-has-unread', unread > 0);
}

// ── Painel — posição 100% via CSS (fixed top-right), sem cálculo JS ─
function toggleNotifPanel() {
    const panel = document.getElementById('notif-panel');
    if (!panel) return;
    const opening = !panel.classList.contains('notif-open');
    panel.classList.toggle('notif-open', opening);
    if (opening) _notifPopulateList();
}

document.addEventListener('click', e => {
    const panel = document.getElementById('notif-panel');
    const btn   = document.getElementById('notif-bell-btn');
    if (panel && btn && !panel.contains(e.target) && !btn.contains(e.target))
        panel.classList.remove('notif-open');
});

function _notifRefreshPanel() {
    const panel = document.getElementById('notif-panel');
    if (panel && panel.classList.contains('notif-open')) _notifPopulateList();
}

function _notifRelTime(iso) {
    try {
        const d   = new Date(iso);
        const abs = d.toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
        const s = Math.floor((Date.now() - d.getTime()) / 1000);
        let rel = '';
        if (s < 60)       rel = 'agora mesmo';
        else if (s < 3600) rel = `há ${Math.floor(s / 60)} min`;
        else if (s < 86400) rel = `há ${Math.floor(s / 3600)} h`;
        return rel ? `${abs} · ${rel}` : abs;
    } catch { return ''; }
}

function _notifIcon(type) {
    return { offline:'bi-wifi-off', online:'bi-wifi', health_atencao:'bi-exclamation-triangle-fill',
             health_critico:'bi-exclamation-octagon-fill' }[type] || 'bi-bell-fill';
}
function _notifColor(type) {
    return { offline:'notif-color-danger', online:'notif-color-success',
             health_atencao:'notif-color-warning', health_critico:'notif-color-danger' }[type] || 'notif-color-info';
}

function _notifPopulateList() {
    const list  = _notifLoad();
    const ul    = document.getElementById('notif-list');
    const empty = document.getElementById('notif-empty');
    if (!ul) return;

    if (!list.length) {
        ul.innerHTML = '';
        if (empty) empty.classList.remove('d-none');
        return;
    }
    if (empty) empty.classList.add('d-none');

    ul.innerHTML = list.map(n => `
        <div class="notif-item ${n.read ? 'notif-read' : 'notif-unread'}" data-id="${n.id}" onclick="_notifMarkRead('${n.id}')">
            <div class="notif-item-icon ${_notifColor(n.type)}">
                <i class="bi ${_notifIcon(n.type)}"></i>
            </div>
            <div class="notif-item-body">
                <div class="notif-item-title">${escapeHtml(n.title)}</div>
                <div class="notif-item-msg">${escapeHtml(n.message)}</div>
                <div class="notif-item-time"><i class="bi bi-clock me-1"></i>${_notifRelTime(n.timestamp)}</div>
            </div>
            ${!n.read ? '<span class="notif-dot"></span>' : ''}
        </div>`).join('');
}

function _notifMarkRead(id) {
    const list = _notifLoad().map(n => n.id === id ? { ...n, read: true } : n);
    _notifSave(list);
    _notifRefreshBell();
    _notifPopulateList();
}

function notifMarkAllRead() {
    _notifSave(_notifLoad().map(n => ({ ...n, read: true })));
    _notifRefreshBell();
    _notifPopulateList();
}

function notifClearAll() {
    _notifSave([]);
    _notifRefreshBell();
    _notifPopulateList();
}

// ── Geração automática ────────────────────────────────────────
function _notifCheckOnlineChange(operadorId, isOnline) {
    if (!_notifPrev.loaded) return;           // primeiro carregamento → não emite
    const prev = _notifPrev.online[operadorId];
    _notifPrev.online[operadorId] = isOnline;
    if (prev === undefined || prev === isOnline) return;

    const op   = (dadosOperadores || []).find(o => o.id === operadorId);
    const nome = op ? op.nome : operadorId;
    const hora = new Date().toLocaleTimeString('pt-BR');

    if (!isOnline) {
        _notifAdd('offline', `${nome} ficou offline`,
            `Comunicação perdida às ${hora}`, operadorId);
    } else {
        _notifAdd('online', `${nome} voltou online`,
            `Conexão restabelecida às ${hora}`, operadorId);
    }
}

function _notifCheckHealthChange(operadorId, nivel, motivos) {
    if (!_notifPrev.loaded) return;
    const prev = _notifPrev.nivel[operadorId];
    _notifPrev.nivel[operadorId] = nivel;
    if (prev === undefined || prev === nivel) return;
    if (nivel === 'Normal') return;

    const op   = (dadosOperadores || []).find(o => o.id === operadorId);
    const nome = op ? op.nome : operadorId;
    const type = nivel === 'Crítico' ? 'health_critico' : 'health_atencao';
    const msg  = (motivos && motivos[0]) ? motivos[0] : `Nível ${nivel} detectado.`;
    _notifAdd(type, `${nome} requer atenção`, msg, operadorId);
}

// Inicializa o estado base sem emitir notificações (primeiro load)
function _notifInitBaseState() {
    (dadosOperadores || []).forEach(op => {
        _notifPrev.online[op.id] = !!op.online;
        _notifPrev.nivel[op.id]  = op.nivel_saude || 'Normal';
    });
    _notifPrev.loaded = true;
}

// Hook no carregarOperadores para iniciar estado base após o primeiro carregamento
const _origCarregarOperadores = carregarOperadores;
window.carregarOperadores = async function () {
    await _origCarregarOperadores();
    if (!_notifPrev.loaded) _notifInitBaseState();
};

// Inicializa o bell ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    _notifRefreshBell();
});

/* ============================================================
   MELHORIAS UX/UI — Health Bar, Filtro Offline, Toast, Badge, Som
   Adicionado sem alterar código existente acima
   ============================================================ */

// ---- Estado global das melhorias ----
const _offlineState = {
    offlineIds: new Set(),          // IDs atualmente offline
    pingFired: new Set(),           // IDs que já receberam o ping dos 30s
    timers: {},                     // timers por ID (setTimeout)
    filterMode: 'all',              // 'all' | 'offline'
};

// ---- Inicialização das melhorias ----
document.addEventListener('DOMContentLoaded', function () {
    _initHealthBar();
    _initFilterBar();
    _initToastContainer();
    _initOfflineAudio();
});

// ============================================================
// 1. HEALTH BAR
// ============================================================
function _initHealthBar() {
    const bar = document.getElementById('health-bar');
    if (!bar) return;
    _tickClock();
    setInterval(_tickClock, 1000);
    _fetchHealthMetrics();
    setInterval(_fetchHealthMetrics, 10000);
}

function _tickClock() {
    const el = document.getElementById('hb-clock');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleTimeString('pt-BR');
}

async function _fetchHealthMetrics() {
    try {
        const res = await fetch('/api/server/health');
        if (!res.ok) throw new Error('não ok');
        const d = await res.json();
        _updateMetric('hb-ram',  d.ram_percent  ?? null, '%');
        _updateMetric('hb-disk', d.disk_percent ?? null, '%');
        _updateMetric('hb-temp', d.cpu_temp     ?? null, '°C', 60, 80);
        _updateMetric('hb-net',  d.net_latency  ?? null, 'ms', 80, 150, true);
        _updateStatusDot(d);
    } catch (_) {
        // endpoint ainda não existe — mostra traço
        ['hb-ram','hb-disk','hb-temp','hb-net'].forEach(id => {
            const v = document.getElementById(id + '-val');
            if (v) v.textContent = '—';
        });
    }
}

function _updateMetric(prefix, value, unit, warnAt = 70, critAt = 90, inverse = false) {
    const valEl  = document.getElementById(prefix + '-val');
    const fillEl = document.getElementById(prefix + '-fill');
    if (!valEl || !fillEl) return;

    if (value === null || value === undefined) { valEl.textContent = '—'; return; }

    valEl.textContent = Math.round(value) + unit;

    // Largura da barra (para latência, escala até 300ms)
    const pct = inverse ? Math.min((value / 300) * 100, 100) : Math.min(value, 100);
    fillEl.style.width = pct + '%';

    // Cor
    const isWarn = inverse ? value >= warnAt : value >= warnAt;
    const isCrit = inverse ? value >= critAt : value >= critAt;
    fillEl.classList.toggle('warn', isWarn && !isCrit);
    fillEl.classList.toggle('crit', isCrit);
}

function _updateStatusDot(d) {
    const dot = document.getElementById('hb-dot');
    if (!dot) return;
    const ram  = d.ram_percent  ?? 0;
    const disk = d.disk_percent ?? 0;
    const temp = d.cpu_temp     ?? 0;
    const net  = d.net_latency  ?? 0;
    const crit = ram > 90 || disk > 90 || temp > 80 || net > 150;
    dot.classList.toggle('crit-static', crit);
    dot.classList.toggle('pulse-ok', !crit);
}

// ============================================================
// 2. FILTRO RÁPIDO OFFLINE
// ============================================================
function _initFilterBar() {
    const btnAll     = document.getElementById('filter-all');
    const btnOffline = document.getElementById('filter-offline');
    if (!btnAll || !btnOffline) return;

    btnAll.addEventListener('click', () => {
        _offlineState.filterMode = 'all';
        btnAll.classList.add('active');
        btnOffline.classList.remove('active');
        _applyFilter();
    });

    btnOffline.addEventListener('click', () => {
        _offlineState.filterMode = 'offline';
        btnOffline.classList.add('active');
        btnAll.classList.remove('active');
        _applyFilter();
    });
}

function _applyFilter() {
    const isOfflineMode = _offlineState.filterMode === 'offline';
    document.querySelectorAll('.operador-item').forEach(item => {
        const id = item.id.replace('operador-item-', '');
        const op = dadosOperadores.find(o => o.id === id);
        if (!op) return;
        if (isOfflineMode && op.online) {
            item.classList.add('hidden-by-filter');
        } else {
            item.classList.remove('hidden-by-filter');
        }
    });
    // Reaplica o filtro de texto se existir
    filtrarOperadores();
}

function _updateOfflineBadge() {
    const badge = document.getElementById('offline-count-badge');
    const count = _offlineState.offlineIds.size;
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count;
        badge.classList.add('visible');
    } else {
        badge.classList.remove('visible');
    }
}

// ============================================================
// 3. BORDA LATERAL DE STATUS NOS CARDS — removida a pedido do usuário
// ============================================================
function _updateCardStatusBorder(operadorId, isOnline) {
    // Desabilitado: bordas coloridas removidas
}

// ============================================================
// 4. TOAST + SOM (disparo único aos 30s offline)
// ============================================================
let _offlineAudioCtx = null;

function _initOfflineAudio() {
    // AudioContext criado sob demanda para compatibilidade com autoplay policy
}

function _initToastContainer() {
    if (!document.getElementById('toast-container')) {
        const tc = document.createElement('div');
        tc.id = 'toast-container';
        document.body.appendChild(tc);
    }
}

function _playOfflinePing() {
    try {
        if (!_offlineAudioCtx) {
            _offlineAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = _offlineAudioCtx;
        // Ping curto: onda senoidal 880Hz, fade out rápido
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.35, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.5);
    } catch (_) { /* silencia em ambientes sem áudio */ }
}

function _showOfflineToast(operadorNome) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'offline-toast';
    toast.innerHTML = `
        <div class="toast-title"><span class="toast-dot"></span>Ponto Offline</div>
        <div class="toast-sector">${escapeHtml(operadorNome)}</div>
        <div class="toast-time">Sem resposta há 30s</div>`;
    container.appendChild(toast);

    // Remove após 8 segundos
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 400);
    }, 8000);
}

// ============================================================
// 5. HOOK NO CICLO DE VIDA DO OPERADOR
//    Intercepta atualizarOperadorNaTela para acionar melhorias
// ============================================================
const _originalAtualizarOperador = atualizarOperadorNaTela;

// Sobrescreve sem remover a lógica original
window.atualizarOperadorNaTela = function (operadorId, data) {
    // Chama lógica original primeiro
    _originalAtualizarOperador(operadorId, data);

    const isOnline = !!data.online;

    // Notificações de online/offline
    _notifCheckOnlineChange(operadorId, isOnline);

    // Atualiza borda lateral
    _updateCardStatusBorder(operadorId, isOnline);

    if (!isOnline) {
        // Acrescenta ao conjunto de offline
        _offlineState.offlineIds.add(operadorId);

        // Inicia timer de 30s se ainda não foi disparado para este ID
        if (!_offlineState.timers[operadorId] && !_offlineState.pingFired.has(operadorId)) {
            _offlineState.timers[operadorId] = setTimeout(() => {
                _offlineState.pingFired.add(operadorId);
                delete _offlineState.timers[operadorId];

                // Obtém nome do operador para o toast
                const op = dadosOperadores.find(o => o.id === operadorId);
                const nome = op ? op.nome : operadorId;

                _playOfflinePing();
                _showOfflineToast(nome);
            }, 30000);
        }
    } else {
        // Voltou online — limpa estado
        _offlineState.offlineIds.delete(operadorId);
        _offlineState.pingFired.delete(operadorId);
        if (_offlineState.timers[operadorId]) {
            clearTimeout(_offlineState.timers[operadorId]);
            delete _offlineState.timers[operadorId];
        }
    }

    _updateOfflineBadge();

    // Reaplica filtro caso esteja no modo offline
    if (_offlineState.filterMode === 'offline') {
        _applyFilter();
    }
};

// Também hook no renderizarOperadores para aplicar bordas após renderização completa
const _originalRenderizarOperadores = renderizarOperadores;
window.renderizarOperadores = function () {
    _originalRenderizarOperadores();
    // Aplica bordas após render
    if (dadosOperadores) {
        dadosOperadores.forEach(op => {
            _updateCardStatusBorder(op.id, !!op.online);
            if (!op.online) {
                _offlineState.offlineIds.add(op.id);
            }
        });
        _updateOfflineBadge();
        _applyFilter();
    }
};

