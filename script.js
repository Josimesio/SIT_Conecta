const els = {
  dataAtualizacao: document.getElementById('dataAtualizacao'),
  globalPercent: document.getElementById('globalPercent'),
  ringProgress: document.getElementById('ringProgress'),
  motivationalTag: document.getElementById('motivationalTag'),
  totalCenarios: document.getElementById('totalCenarios'),
  totalConcluidos: document.getElementById('totalConcluidos'),
  totalEmAndamento: document.getElementById('totalEmAndamento'),
  totalNaoIniciado: document.getElementById('totalNaoIniciado'),
  totalBloqueados: document.getElementById('totalBloqueados'),
  totalCancelados: document.getElementById('totalCancelados'),
  totalOcorrenciasAbertas: document.getElementById('totalOcorrenciasAbertas'),
  headlineCallout: document.getElementById('headlineCallout'),
  headlinePill: document.getElementById('headlinePill'),
  leaderboard: document.getElementById('leaderboard'),
  statusBars: document.getElementById('statusBars'),
  areaBoard: document.getElementById('areaBoard'),
  focusTable: document.getElementById('focusTable'),
  occurrenceBoard: document.getElementById('occurrenceBoard')
};

const RING_CIRCUMFERENCE = 301.59;
const AUTO_CSV_NAME = 'Cenarios_Consolidados_atualizado.csv';
const AUTO_CSV_PATH = `output/${AUTO_CSV_NAME}`;
const AUTO_REFRESH_INTERVAL_MS = 180000; // 3 minutos
let lastCsvLoadOk = false;
let lastCsvSource = '';
let lastDataAtualizacaoValue = '';

const motivationalMessages = [
  { threshold: 0, tag: 'Mapa inicial', title: 'Dados carregados. Agora a leitura é de saúde, risco e destravamento.', pill: 'Gestão por evidência' },
  { threshold: 20, tag: 'Execução em movimento', title: 'Há avanço, mas ainda existe estoque de cenário parado para priorizar.', pill: 'Atenção aos gargalos' },
  { threshold: 40, tag: 'Ritmo consistente', title: 'A execução ganhou corpo. O próximo passo é atacar bloqueios e dependências.', pill: 'Remover travas' },
  { threshold: 60, tag: 'Boa cadência', title: 'A maior parte já andou. Agora a gestão precisa proteger o fluxo e decidir rápido.', pill: 'Decisão e foco' },
  { threshold: 80, tag: 'Reta de estabilização', title: 'Poucos itens concentram o risco. Ação cirúrgica agora evita ruído no fechamento.', pill: 'Fechar pendências' },
  { threshold: 100, tag: 'Execução estabilizada', title: 'Todos os cenários concluídos. A base está pronta para auditoria e sustentação.', pill: 'Fluxo fechado' }
];

document.addEventListener('DOMContentLoaded', () => {
  initPageLoader();
  showPageLoader('Sincronizando dados do GTN...', 'Lendo o CSV consolidado e montando a visão.');
  initViewSelector();
  tryAutoLoadCsv({ showLoader: true });

  setInterval(() => {
    tryAutoLoadCsv({ showLoader: false });
  }, AUTO_REFRESH_INTERVAL_MS);
});

window.addEventListener('beforeunload', () => {
  showPageLoader('Abrindo nova visão...', 'Preparando o painel selecionado.');
});

function initPageLoader() {
  if (document.getElementById('pageLoader')) return;

  const style = document.createElement('style');
  style.id = 'pageLoaderStyle';
  style.textContent = `
    .page-loader {
      position: fixed;
      inset: 0;
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background:
        radial-gradient(circle at top left, rgba(124, 92, 255, 0.34), transparent 34%),
        radial-gradient(circle at bottom right, rgba(20, 211, 166, 0.24), transparent 36%),
        rgba(5, 10, 28, 0.88);
      backdrop-filter: blur(12px);
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transition: opacity 0.22s ease, visibility 0.22s ease;
    }

    .page-loader.is-active {
      opacity: 1;
      visibility: visible;
      pointer-events: all;
    }

    .loader-box {
      width: min(420px, 100%);
      border-radius: 28px;
      padding: 30px 28px;
      text-align: center;
      color: #f5f7ff;
      background:
        linear-gradient(135deg, rgba(24, 35, 74, 0.92), rgba(11, 36, 48, 0.90));
      border: 1px solid rgba(255, 255, 255, 0.14);
      box-shadow: 0 28px 80px rgba(0, 0, 0, 0.40);
    }

    .loader-spinner {
      width: 66px;
      height: 66px;
      margin: 0 auto 18px;
      border-radius: 999px;
      border: 7px solid rgba(255, 255, 255, 0.14);
      border-top-color: #fff29a;
      border-right-color: #14d3a6;
      animation: loaderSpin 0.85s linear infinite;
    }

    .loader-box strong {
      display: block;
      font-size: 1.18rem;
      font-weight: 800;
      margin-bottom: 8px;
    }

    .loader-box span {
      display: block;
      color: #b8c6ef;
      font-size: 0.95rem;
      line-height: 1.35;
    }

    .loader-dots::after {
      content: '';
      animation: loaderDots 1.2s steps(4, end) infinite;
    }

    @keyframes loaderSpin {
      to { transform: rotate(360deg); }
    }

    @keyframes loaderDots {
      0% { content: ''; }
      25% { content: '.'; }
      50% { content: '..'; }
      75%, 100% { content: '...'; }
    }
  `;

  const loader = document.createElement('div');
  loader.id = 'pageLoader';
  loader.className = 'page-loader';
  loader.innerHTML = `
    <div class="loader-box" role="status" aria-live="polite">
      <div class="loader-spinner" aria-hidden="true"></div>
      <strong id="pageLoaderTitle" class="loader-dots">Sincronizando dados do GTN</strong>
      <span id="pageLoaderText">Lendo o CSV consolidado e preparando o painel.</span>
    </div>
  `;

  document.head.appendChild(style);
  document.body.appendChild(loader);
}

function showPageLoader(title = 'Sincronizando dados do GTN...', text = 'Lendo o CSV consolidado e montando a visão.') {
  const loader = document.getElementById('pageLoader');
  if (!loader) return;

  const titleEl = document.getElementById('pageLoaderTitle');
  const textEl = document.getElementById('pageLoaderText');

  if (titleEl) titleEl.textContent = title;
  if (textEl) textEl.textContent = text;

  loader.classList.add('is-active');
}

function hidePageLoader() {
  const loader = document.getElementById('pageLoader');
  if (!loader) return;

  window.setTimeout(() => {
    loader.classList.remove('is-active');
  }, 250);
}

function initViewSelector() {
  const selector = document.getElementById('viewSelector');
  if (!selector) return;

  const currentPage = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
  const currentOption = [...selector.options].find(option => option.value.toLowerCase() === currentPage);

  if (currentOption) {
    selector.value = currentOption.value;
  }

  selector.addEventListener('change', () => {
    const targetPage = selector.value;
    if (!targetPage || targetPage.toLowerCase() === currentPage) return;

    const selectedLabel = selector.options[selector.selectedIndex]?.textContent?.trim() || 'nova visão';
    showPageLoader('Abrindo nova visão...', `Carregando ${selectedLabel} e sincronizando o CSV.`);

    window.setTimeout(() => {
      window.location.assign(targetPage);
    }, 120);
  });
}
async function tryAutoLoadCsv(options = {}) {
  const { showLoader = false } = options;
  const candidates = getCsvCandidates();
  const isInitialLoad = !lastCsvLoadOk;

  if (showLoader) {
    showPageLoader('Sincronizando dados do GTN...', 'Lendo o CSV consolidado e montando a visão selecionada.');
  }

  if (isInitialLoad) {
    setGeneratedAt(`Lendo ${AUTO_CSV_PATH}...`);
  }

  for (const candidate of candidates) {
    try {
      const response = await fetch(withCacheBuster(candidate), { cache: 'no-store' });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const buffer = await response.arrayBuffer();
      const text = decodeCsvBuffer(buffer);
      parseCsvText(text);

      lastCsvLoadOk = true;
      lastCsvSource = candidate;

      if (showLoader) hidePageLoader();
      return true;
    } catch (error) {
      console.warn(`Falha ao carregar CSV em ${candidate}:`, error);
    }
  }

  const message = `Arquivo processado não encontrado. Verifique se existe ${AUTO_CSV_PATH}.`;

  // Proteção importante: se os dados já foram carregados uma vez, não sobrescreve
  // o cabeçalho com falso erro em atualização automática. Mantém o último CSV bom.
  if (!lastCsvLoadOk) {
    setGeneratedAt(message);
  } else if (lastDataAtualizacaoValue) {
    setGeneratedAt(`${lastDataAtualizacaoValue} · último carregamento válido`);
  }

  if (showLoader) {
    if (!lastCsvLoadOk) {
      showPageLoader('Não foi possível carregar os dados', `Verifique se o arquivo ${AUTO_CSV_PATH} existe na pasta output.`);
      window.setTimeout(hidePageLoader, 1800);
    } else {
      hidePageLoader();
    }
  }

  return false;
}

function getCsvCandidates() {
  const currentPath = window.location.pathname || '';
  const currentDir = currentPath.replace(/[^/]*$/, '');
  const repoBase = currentDir.split('/').filter(Boolean)[0] || '';
  const repoRelative = repoBase ? `/${repoBase}/${AUTO_CSV_PATH}` : '';

  return [
    AUTO_CSV_PATH,
    `./${AUTO_CSV_PATH}`,
    repoRelative
  ].filter(Boolean).filter((value, index, array) => array.indexOf(value) === index);
}

function withCacheBuster(path) {
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}v=${Date.now()}`;
}

function decodeCsvBuffer(buffer) {
  const utf8 = new TextDecoder('utf-8', { fatal: false }).decode(buffer);
  if (!utf8.includes('�')) return utf8;
  return new TextDecoder('windows-1252', { fatal: false }).decode(buffer);
}

function parseCsvText(text) {
  const parsed = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
    delimiter: detectDelimiter(text),
    quoteChar: '"'
  });

  const rows = parsed.data || [];
  renderDashboard(rows);
  updateGeneratedAt(rows);
}

function detectDelimiter(text) {
  const firstLine = String(text || '').split(/\r?\n/).find(line => line.trim()) || '';
  const candidates = [';', ',', '\t', '|'];
  return candidates
    .map(delimiter => ({ delimiter, count: firstLine.split(delimiter).length - 1 }))
    .sort((a, b) => b.count - a.count)[0]?.delimiter || ';';
}

function updateGeneratedAt(rows) {
  if (!els.dataAtualizacao) return;

  if (!rows.length) {
    setGeneratedAt('CSV sem dados para exibir.');
    return;
  }

  const generatedAt = getValue(rows[0], 'Gerado em');
  if (generatedAt) {
    lastDataAtualizacaoValue = generatedAt;
    setGeneratedAt(generatedAt);
  } else {
    setGeneratedAt("Coluna 'Gerado em' não encontrada no CSV processado.");
  }
}

function setGeneratedAt(message) {
  if (els.dataAtualizacao) {
    els.dataAtualizacao.textContent = message;
  }
}

function normalize(text = '') {
  return String(text)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function findKey(row, target) {
  const entries = Object.keys(row).map(key => [key, normalize(key)]);
  const hit = entries.find(([, norm]) => norm === normalize(target));
  return hit ? hit[0] : null;
}

function getValue(row, target, fallback = '') {
  const key = findKey(row, target);
  return key ? row[key] : fallback;
}

function getFirstValue(row, targets, fallback = '') {
  for (const target of targets) {
    const value = getValue(row, target, '');
    if (String(value ?? '').trim() !== '') return value;
  }
  return fallback;
}

function getOpenOccurrenceCount(row, occurrenceStatus, occurrenceDescription, scenarioStatus) {
  const countFields = [
    'Ocorrências abertas',
    'Ocorrencias abertas',
    'Ocorrências Abertas',
    'Ocorrencias Abertas',
    'Qtd Ocorrências Abertas',
    'Qtd Ocorrencias Abertas',
    'Qtde Ocorrências Abertas',
    'Qtde Ocorrencias Abertas',
    'Quantidade de Ocorrências Abertas',
    'Quantidade de Ocorrencias Abertas'
  ];

  for (const field of countFields) {
    const value = getValue(row, field, '');
    const parsed = Number(String(value).replace(',', '.').replace(/[^0-9.]/g, ''));
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }

  const hasOccurrenceText = hasMeaningfulOccurrenceText(occurrenceDescription);
  if (hasOccurrenceText && !isOccurrenceClosed(occurrenceStatus)) return 1;

  // Fallback prático: quando o CSV ainda não tem colunas próprias de ocorrência,
  // tratamos cenário Bloqueado como ocorrência aberta para o painel não ficar cego.
  if (!hasOccurrenceText && !String(occurrenceStatus || '').trim() && isBlocked(scenarioStatus)) return 1;

  return 0;
}

function hasMeaningfulOccurrenceText(value) {
  const text = normalize(value);
  if (!text) return false;
  return !['0', '-', 'nao', 'nao informado', 'sem ocorrencia', 'sem ocorrencias', 'n/a', 'na'].includes(text);
}

function isOccurrenceClosed(status) {
  const s = normalize(status);
  if (!s) return false;
  return s.includes('fechad') || s.includes('concluid') || s.includes('resolvid') || s.includes('cancelad') || s.includes('encerrad') || s === 'closed' || s === 'done';
}


function renderDashboard(rows) {
  const cleanRows = rows
    .filter(row => Object.values(row).some(v => String(v).trim() !== ''))
    .map(row => {
      const ocorrenciaStatus = getFirstValue(row, [
        'Status da Ocorrência',
        'Status Ocorrência',
        'Status da Ocorrencia',
        'Status Ocorrencia',
        'Situação da Ocorrência',
        'Situacao da Ocorrencia',
        'Situação Ocorrência',
        'Situacao Ocorrencia'
      ]);
      const ocorrenciaDescricao = getFirstValue(row, [
        'Ocorrência',
        'Ocorrencia',
        'Descrição da Ocorrência',
        'Descricao da Ocorrencia',
        'Ocorrência Aberta',
        'Ocorrencia Aberta',
        'Observação da Ocorrência',
        'Observacao da Ocorrencia'
      ]);
      const statusOriginal = getValue(row, 'Status') || 'Sem status';
      const ocorrenciasAbertasQtd = getOpenOccurrenceCount(row, ocorrenciaStatus, ocorrenciaDescricao, statusOriginal);

      return {
        identificador: getValue(row, 'Identificador'),
        cenario: getValue(row, 'Cenário') || getValue(row, 'Cenario'),
        area: getValue(row, 'Área de Negócio') || getValue(row, 'Area de Negocio') || 'Não informada',
        frente: getValue(row, 'Frente') || getValue(row, 'Área de Negócio') || getValue(row, 'Area de Negocio') || 'Não informada',
        lider: getValue(row, 'Lider do Cenário') || getValue(row, 'Líder do Cenário') || 'Sem líder',
        statusOriginal,
        prioridade: getValue(row, 'Grupo de Prioridade'),
        execucoes: Number(String(getValue(row, 'Qtde. Execuções Concluídas') || '0').replace(',', '.')) || 0,
        ocorrenciaStatus,
        ocorrenciaDescricao,
        ocorrenciasAbertasQtd
      };
    });

  const total = cleanRows.length;
  const concluded = cleanRows.filter(row => isConcluded(row.statusOriginal)).length;
  const inProgress = cleanRows.filter(row => isInProgress(row.statusOriginal)).length;
  const blocked = cleanRows.filter(row => isBlocked(row.statusOriginal)).length;
  const notStarted = cleanRows.filter(row => isNotStarted(row.statusOriginal)).length;
  const cancelled = cleanRows.filter(row => isCancelled(row.statusOriginal)).length;
  const percent = getPercent(concluded, total);

  updateSummary(total, concluded, inProgress, notStarted, blocked, cancelled, percent);
  renderLeaderboard(cleanRows);
  renderStatusBars(total, concluded, inProgress, notStarted, blocked, cancelled);
  renderAreaBoard(cleanRows);
  renderFocusTable(cleanRows);
  renderOccurrenceBoard(cleanRows);
}

function updateSummary(total, concluded, inProgress, notStarted, blocked, cancelled, percent) {
  if (els.totalCenarios) els.totalCenarios.textContent = total.toLocaleString('pt-BR');
  if (els.totalConcluidos) els.totalConcluidos.textContent = concluded.toLocaleString('pt-BR');
  if (els.totalEmAndamento) els.totalEmAndamento.textContent = inProgress.toLocaleString('pt-BR');
  if (els.totalNaoIniciado) els.totalNaoIniciado.textContent = notStarted.toLocaleString('pt-BR');
  if (els.totalBloqueados) els.totalBloqueados.textContent = blocked.toLocaleString('pt-BR');
  if (els.totalCancelados) els.totalCancelados.textContent = cancelled.toLocaleString('pt-BR');
  if (els.globalPercent) els.globalPercent.textContent = formatPercent(percent);
  if (els.ringProgress) els.ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE * (1 - percent / 100)}`;

  const currentMessage = [...motivationalMessages].reverse().find(item => percent >= item.threshold) || motivationalMessages[0];
  if (els.motivationalTag) els.motivationalTag.textContent = currentMessage.tag;
  if (els.headlineCallout) els.headlineCallout.textContent = currentMessage.title;
  if (els.headlinePill) els.headlinePill.textContent = currentMessage.pill;
}

function renderLeaderboard(rows) {
  if (!els.leaderboard) return;
  if (!rows.length) {
    els.leaderboard.innerHTML = 'Nenhum dado disponível.';
    return;
  }

  const grouped = new Map();

  rows.forEach(row => {
    const key = row.lider || 'Sem líder';
    if (!grouped.has(key)) {
      grouped.set(key, { lider: key, total: 0, concluded: 0, inProgress: 0 });
    }
    const item = grouped.get(key);
    item.total += 1;
    if (isConcluded(row.statusOriginal)) item.concluded += 1;
    if (isInProgress(row.statusOriginal)) item.inProgress += 1;
  });

  const ranking = [...grouped.values()]
    .map(item => ({ ...item, percent: getPercent(item.concluded, item.total) }))
    .sort((a, b) => b.concluded - a.concluded || b.percent - a.percent || a.lider.localeCompare(b.lider, 'pt-BR'))
    .slice(0, 21);

  const podium = ranking.slice(0, 3);
  const rest = ranking.slice(3);
  const champion = podium[0];
  const chasers = podium.slice(1);

  const championHtml = champion ? `
    <div class="leader-spotlight">
      <div class="leader-spotlight-top">
        <div>
          <div class="leader-crown">Referência de avanço consolidado</div>
          <h4 class="leader-spotlight-name">${escapeHtml(champion.lider)}</h4>
          <div class="leader-spotlight-meta">
            ${champion.concluded} concluídos de ${champion.total} cenários · ${champion.inProgress} em andamento
          </div>
        </div>
        <div class="leader-spotlight-score">
          <strong>${formatPercent(champion.percent)}</strong>
          <span>avanço</span>
        </div>
      </div>
      <div class="leader-spotlight-track">
        <div class="leader-spotlight-fill" style="width:${percentWidth(champion.percent)}%"></div>
      </div>
    </div>
  ` : '';

  const chasersHtml = chasers.length ? `
    <div class="leaderboard-chasers">
      ${chasers.map((item, index) => `
        <div class="chaser-card ${index === 0 ? 'top-2' : ''} ${index === 1 ? 'top-3' : ''}">
          <div class="chaser-head">
            <div>
              <div class="chaser-place">#${index + 2}</div>
            </div>
            <div class="chaser-score">
              <strong>${formatPercent(item.percent)}</strong>
              <span>avanço</span>
            </div>
          </div>
          <div class="chaser-name">${escapeHtml(item.lider)}</div>
          <div class="chaser-meta">${item.concluded} concluídos · ${item.total} cenários · ${item.inProgress} em andamento</div>
        </div>
      `).join('')}
    </div>
  ` : '';

  const restHtml = rest.length ? `
    <div class="leaderboard-rest">
      <div class="leaderboard-rest-title">Demais responsáveis</div>
      <div class="leaderboard-rest-list">
        ${rest.map((item, index) => `
          <div class="leaderboard-rest-row">
            <div class="rest-position">#${index + 4}</div>
            <div class="rest-main">
              <strong>${escapeHtml(item.lider)}</strong>
              <span>${item.concluded} concluídos de ${item.total} cenários · ${item.inProgress} em andamento</span>
            </div>
            <div class="rest-percent">${formatPercent(item.percent)}</div>
          </div>
        `).join('')}
      </div>
    </div>
  ` : '';

  els.leaderboard.innerHTML = `
    <div class="leaderboard-stage">
      ${championHtml}
      ${chasersHtml}
      ${restHtml}
    </div>
  `;

}

function renderStatusBars(total, concluded, inProgress, notStarted, blocked, cancelled) {
  if (!els.statusBars) return;
  const other = Math.max(total - concluded - inProgress - notStarted - blocked - cancelled, 0);
  const statuses = [
    { label: 'Concluído', value: concluded, percent: getPercent(concluded, total), color: 'linear-gradient(90deg, #14d3a6, #7dffd8)' },
    { label: 'Em andamento', value: inProgress, percent: getPercent(inProgress, total), color: 'linear-gradient(90deg, #ffb84d, #ffd88d)' },
    { label: 'Bloqueado', value: blocked, percent: getPercent(blocked, total), color: 'linear-gradient(90deg, #ff4d6d, #ff8fa3)' },
    { label: 'Não iniciado', value: notStarted, percent: getPercent(notStarted, total), color: 'linear-gradient(90deg, #7c5cff, #b7a6ff)' },
    { label: 'Cancelado', value: cancelled, percent: getPercent(cancelled, total), color: 'linear-gradient(90deg, #98a7d8, #cad5ff)' },
    { label: 'Outros', value: other, percent: getPercent(other, total), color: 'linear-gradient(90deg, #8a94a6, #c6ccd8)' }
  ];

  els.statusBars.innerHTML = statuses.map(item => `
    <div class="status-item">
      <div class="status-head">
        <strong>${item.label}</strong>
        <span>${item.value} · ${formatPercent(item.percent)}</span>
      </div>
      <div class="status-track">
        <div class="status-fill" style="width:${percentWidth(item.percent)}%; background:${item.color}"></div>
      </div>
    </div>
  `).join('');
}

function renderAreaBoard(rows) {
  if (!els.areaBoard) return;
  if (!rows.length) {
    els.areaBoard.innerHTML = 'Nenhum dado disponível.';
    return;
  }

  const grouped = new Map();
  rows.forEach(row => {
    const key = row.frente || row.area || 'Não informada';
    if (!grouped.has(key)) {
      grouped.set(key, { frente: key, total: 0, concluded: 0, inProgress: 0, blocked: 0, notStarted: 0, leaders: new Set() });
    }
    const item = grouped.get(key);
    item.total += 1;
    if (isConcluded(row.statusOriginal)) item.concluded += 1;
    if (isInProgress(row.statusOriginal)) item.inProgress += 1;
    if (isBlocked(row.statusOriginal)) item.blocked += 1;
    if (isNotStarted(row.statusOriginal)) item.notStarted += 1;
    item.leaders.add(row.lider || 'Sem líder');
  });

  const cards = [...grouped.values()]
    .map(item => {
      const leaderNames = [...item.leaders]
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, 'pt-BR'));

      return {
        ...item,
        leaderNames,
        leaderTooltip: leaderNames.join('\n'),
        percent: getPercent(item.concluded, item.total),
        leaderCount: leaderNames.length
      };
    })
    .sort((a, b) => b.percent - a.percent || b.concluded - a.concluded || a.frente.localeCompare(b.frente, 'pt-BR'));

  els.areaBoard.innerHTML = cards.map(item => `
    <div class="area-card front-card">
      <div class="area-top">
        <div>
          <div class="front-label">Frente</div>
          <div class="area-title">${escapeHtml(item.frente)}</div>
        </div>
        <div class="area-badge">${formatPercent(item.percent)}</div>
      </div>
      <div class="status-track" style="margin-top:12px;">
        <div class="status-fill" style="width:${percentWidth(item.percent)}%; background: linear-gradient(90deg, #7c5cff, #14d3a6);"></div>
      </div>
      <div class="area-stats front-stats">
        <span>${item.concluded}/${item.total} concluídos</span>
        <span>${item.inProgress} em andamento</span>
        <span>${item.blocked} bloqueados</span>
        <span>${item.notStarted} não iniciados</span>
        <span class="tooltip-trigger" tabindex="0" data-tooltip="${escapeHtml(item.leaderTooltip)}" aria-label="Líderes da frente ${escapeHtml(item.frente)}">${item.leaderCount} líder(es)</span>
      </div>
    </div>
  `).join('');
}


function renderOccurrenceBoard(rows) {
  if (!els.occurrenceBoard || !els.totalOcorrenciasAbertas) return;

  const grouped = new Map();

  rows.forEach(row => {
    const qtd = Number(row.ocorrenciasAbertasQtd) || 0;
    if (qtd <= 0) return;

    const key = row.identificador || row.cenario || 'Cenário sem identificação';
    if (!grouped.has(key)) {
      grouped.set(key, {
        identificador: row.identificador || '-',
        cenario: row.cenario || 'Cenário sem nome',
        lider: row.lider || 'Sem líder',
        frente: row.frente || row.area || 'Não informada',
        status: row.statusOriginal || '-',
        ocorrencias: 0,
        detalhes: []
      });
    }

    const item = grouped.get(key);
    item.ocorrencias += qtd;
    if (row.ocorrenciaDescricao) item.detalhes.push(row.ocorrenciaDescricao);
  });

  const cards = [...grouped.values()]
    .sort((a, b) => b.ocorrencias - a.ocorrencias || a.cenario.localeCompare(b.cenario, 'pt-BR'));

  const total = cards.reduce((sum, item) => sum + item.ocorrencias, 0);
  els.totalOcorrenciasAbertas.textContent = total.toLocaleString('pt-BR');

  if (!cards.length) {
    els.occurrenceBoard.innerHTML = '<div class="occurrence-empty">Sem ocorrências abertas vinculadas aos cenários. Melhor impossível — por enquanto.</div>';
    return;
  }

  els.occurrenceBoard.innerHTML = cards.slice(0, 8).map(item => {
    const detalhes = item.detalhes
      .filter(Boolean)
      .slice(0, 2)
      .map(detail => `<span>📝 ${escapeHtml(detail)}</span>`)
      .join('');

    return `
      <div class="occurrence-item">
        <div class="occurrence-item-top">
          <div>
            <div class="occurrence-scenario">${escapeHtml(item.cenario)}</div>
            <div class="occurrence-meta"><span>${escapeHtml(item.identificador)}</span></div>
          </div>
          <div class="occurrence-count">${item.ocorrencias.toLocaleString('pt-BR')}</div>
        </div>
        <div class="occurrence-meta">
          <span>👤 ${escapeHtml(item.lider)}</span>
          <span>⚔️ ${escapeHtml(item.frente)}</span>
          <span>📌 ${escapeHtml(item.status)}</span>
          ${detalhes}
        </div>
      </div>
    `;
  }).join('');
}

function renderFocusTable(rows) {
  if (!els.focusTable) return;
  const priorityRows = rows
    .filter(row => isBlocked(row.statusOriginal) || isNotStarted(row.statusOriginal))
    .sort((a, b) => compareStatusForUnlock(a.statusOriginal, b.statusOriginal) || comparePriority(a.prioridade, b.prioridade) || b.execucoes - a.execucoes || a.cenario.localeCompare(b.cenario, 'pt-BR'))
    .slice(0, 21);

  if (!priorityRows.length) {
    els.focusTable.innerHTML = '<tr><td colspan="5" class="empty-cell">Sem bloqueados ou não iniciados no momento. A pista limpou.</td></tr>';
    return;
  }

  els.focusTable.innerHTML = priorityRows.map(row => `
    <tr>
      <td>${escapeHtml(row.identificador || '-')}</td>
      <td>${escapeHtml(row.cenario || '-')}</td>
      <td>${escapeHtml(row.lider || '-')}</td>
      <td>${escapeHtml(row.frente || row.area || '-')}</td>
      <td>${statusPill(row.statusOriginal)}</td>
    </tr>
  `).join('');
}

function isConcluded(status) {
  return normalize(status).includes('concluido');
}

function isInProgress(status) {
  const s = normalize(status);
  return s.includes('andamento') || s.includes('em execucao') || s.includes('em progresso');
}

function isBlocked(status) {
  const s = normalize(status);
  return s.includes('bloqueado') || s.includes('impedimento') || s.includes('travado');
}

function isNotStarted(status) {
  const s = normalize(status);
  return s.includes('nao iniciado') || s.includes('não iniciado');
}

function isCancelled(status) {
  const s = normalize(status);
  return s.includes('cancelado') || s.includes('cancelada') || s.includes('cancel');
}

function compareStatusForUnlock(a, b) {
  const weight = status => {
    if (isBlocked(status)) return 2;
    if (isNotStarted(status)) return 1;
    return 0;
  };

  return weight(b) - weight(a);
}

function getPercent(value, total) {
  return total ? Number(((value / total) * 100).toFixed(2)) : 0;
}

function formatPercent(value) {
  const number = Number(value) || 0;
  return `${number.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function percentWidth(value) {
  const number = Number(value) || 0;
  return Math.max(0, Math.min(100, number)).toFixed(2);
}

function comparePriority(a, b) {
  const pa = extractPriorityNumber(a);
  const pb = extractPriorityNumber(b);
  return pb - pa;
}

function extractPriorityNumber(value) {
  const match = String(value || '').match(/\d+/);
  return match ? Number(match[0]) : -1;
}

function statusPill(status) {
  const label = escapeHtml(status || '-');
  let className = 'neutral';

  if (isConcluded(status)) className = 'status-concluido';
  else if (isInProgress(status)) className = 'status-andamento';
  else if (isBlocked(status)) className = 'status-bloqueado';
  else if (isNotStarted(status)) className = 'status-nao-iniciado';
  else if (isCancelled(status)) className = 'status-cancelado';
  else className = 'status-outro';

  return `<span class="status-pill ${className}">${label}</span>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
