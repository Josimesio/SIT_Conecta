"""Download independente de Ocorrencias do GTN - plano SIT02.

Base: navegacao V2 validada pelo usuario em 16/10/2026.
Requer as mesmas dependencias do script completo: playwright e python-dotenv.
Coloque este arquivo na mesma pasta do .env com GTN_USER e GTN_PASS.
Saida: output/Ocorrencias_Consolidadas_atualizado.csv.
Log: execucao_ocorrencias.log. Lock compartilhado: rodando.lock.

Execucao: python Script_Somente_Ocorrencias_SIT02.py
"""

from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page
from datetime import datetime
from urllib.parse import unquote, urljoin, urlsplit
import os
import time
import traceback
import csv
import re
import unicodedata

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GTN_URL = os.getenv("GTN_URL", "https://gtn.ninecon.com.br/ords/r/gtn/gtn/login?tz=-3:00")
GTN_HOME_URL = os.getenv("GTN_HOME_URL", "https://gtn.ninecon.com.br/ords/r/gtn/gtn/home")
GTN_USER = os.getenv("GTN_USER")
GTN_PASS = os.getenv("GTN_PASS")
GTN_PLANO_TESTE = os.getenv(
    "GTN_PLANO_TESTE", "PLANO DE TESTES INTEGRADOS PROGRAMA CONECTA SIT02 (Em Execução)"
).strip()

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
LOCK_FILE = BASE_DIR / "rodando.lock"
LOG_FILE = BASE_DIR / "execucao_ocorrencias.log"

DOWNLOAD_TIMEOUT_MS = int(os.getenv("GTN_DOWNLOAD_TIMEOUT_MS", "180000"))
DEFAULT_TIMEOUT_MS = int(os.getenv("GTN_DEFAULT_TIMEOUT_MS", "60000"))
POST_DOWNLOAD_PAUSE_MS = int(os.getenv("GTN_POST_DOWNLOAD_PAUSE_MS", "2000"))
APEX_REFRESH_TIMEOUT_MS = int(os.getenv("GTN_APEX_REFRESH_TIMEOUT_MS", "45000"))
EXECUCAO_TESTES_READY_TIMEOUT_MS = int(os.getenv("GTN_EXECUCAO_TESTES_READY_TIMEOUT_MS", "120000"))

PADRAO_MENU_EXECUCAO_TESTES = re.compile(
    r"^\s*Execu[cç][aã]o\s+(?:de|dos)\s+Testes?\s*$", re.I
)
ALIASES_EXECUCAO_TESTES = frozenset({
    "execucao-dos-testes", "execucao-de-testes", "execucao-testes", "execucao-de-teste"
})


class ErroNavegacaoExecucaoTestes(RuntimeError):
    """Destino de testes acionado, mas sem confirmacao da grade correta."""


def normalizar_texto_navegacao(texto: str) -> str:
    texto = unicodedata.normalize("NFD", unquote(texto or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return " ".join(texto.casefold().split())


def url_e_execucao_testes(url: str) -> bool:
    alias = urlsplit(url or "").path.rstrip("/").rsplit("/", 1)[-1]
    return normalizar_texto_navegacao(alias) in ALIASES_EXECUCAO_TESTES


def url_tem_sessao(url: str) -> bool:
    try:
        return "session=" in (url or "").lower()
    except Exception:
        return False


def log(msg: str) -> None:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{agora}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def validar_env() -> None:
    faltando = []

    if not GTN_USER:
        faltando.append("GTN_USER")
    if not GTN_PASS:
        faltando.append("GTN_PASS")

    if faltando:
        raise ValueError(f"Variáveis ausentes no .env: {', '.join(faltando)}")


def pagina_aberta(page: Page) -> bool:
    try:
        return (page is not None) and (not page.is_closed())
    except Exception:
        return False


def aguardar_processamento_apex(page: Page, motivo: str = "") -> None:
    if motivo:
        log(f"🌀 Aguardando refresh APEX: {motivo}")

    seletores_loading = [
        ".u-Processing",
        ".u-Processing-spinner",
        ".a-Region-loading",
        ".a-Region--loading",
        ".a-IRR-loading",
        ".a-IRR-icon--processing",
        ".js-regionIsLoading",
        "[aria-busy='true']",
    ]

    for seletor in seletores_loading:
        try:
            page.locator(seletor).first.wait_for(state="hidden", timeout=APEX_REFRESH_TIMEOUT_MS)
        except Exception:
            continue

    page.wait_for_timeout(1200)


def aguardar_estabilidade(page: Page, motivo: str = "") -> None:
    if motivo:
        log(f"⏳ Aguardando estabilidade: {motivo}")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    page.wait_for_timeout(1500)


def aguardar_execucao_testes_renderizada(page: Page, origem: str = "") -> None:
    """Confirma a grade especifica dentro de um unico prazo total.

    Nao usa botoes genericos de outras telas como prova de chegada. A URL
    pode conter acentos codificados; a confirmacao e o select real da grade.
    """
    detalhe = f" ({origem})" if origem else ""
    log(f"🧪 Aguardando renderização completa da Execução de Testes{detalhe}...")
    inicio = time.monotonic()
    prazo = inicio + max(EXECUCAO_TESTES_READY_TIMEOUT_MS, 1) / 1000
    proximo_aviso = inicio + 10

    while True:
        if not pagina_aberta(page):
            raise ErroNavegacaoExecucaoTestes(
                "O navegador foi fechado enquanto a grade de Execução de Testes era aguardada."
            )
        if tela_execucao_testes_ativa(page):
            decorrido = time.monotonic() - inicio
            log(
                f"✅ Grade de Execução de Testes confirmada em {decorrido:.1f}s: "
                "#R35932200234408468_saved_reports visível e habilitado."
            )
            return

        agora = time.monotonic()
        restante = prazo - agora
        if restante <= 0:
            break
        if agora >= proximo_aviso:
            pagina_atual = unquote(urlsplit(page.url).path)
            log(
                f"⏳ A grade específica ainda não apareceu. Página atual: {pagina_atual}. "
                f"Restam {restante:.0f}s do prazo de abertura."
            )
            proximo_aviso = agora + 10
        page.wait_for_timeout(min(500, restante * 1000))

    salvar_debug(page, "execucao_testes_renderizacao_incompleta")
    raise ErroNavegacaoExecucaoTestes(
        "A navegação foi acionada, mas o select específico de Execução de Testes "
        "(#R35932200234408468_saved_reports) não ficou visível e habilitado "
        f"no prazo total de {EXECUCAO_TESTES_READY_TIMEOUT_MS} ms. "
        f"Página atual: {unquote(urlsplit(page.url).path)}. "
        "Confira a captura e o HTML de diagnóstico antes de alterar os seletores."
    )


def salvar_debug(page: Page, nome_base: str) -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = OUTPUT_DIR / f"{nome_base}_{timestamp}.png"
    html_path = OUTPUT_DIR / f"{nome_base}_{timestamp}.html"

    try:
        if not pagina_aberta(page):
            log("⚠️ Página já estava fechada. Debug visual não pôde ser salvo.")
            return

        page.screenshot(path=str(screenshot_path), full_page=False)
        html_path.write_text(page.content(), encoding="utf-8")
        log(f"📸 Screenshot salvo em: {screenshot_path}")
        log(f"📝 HTML salvo em: {html_path}")
    except Exception as e:
        log(f"⚠️ Falha ao salvar debug: {e}")


def fazer_login(page: Page) -> None:
    log("🌐 Abrindo tela de login...")
    page.goto(GTN_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    aguardar_estabilidade(page, "carregamento inicial da tela de login")

    log("🔐 Preenchendo credenciais...")
    page.get_by_role("textbox", name="Usuário").click()
    page.get_by_role("textbox", name="Usuário").fill(GTN_USER)
    page.get_by_role("textbox", name="Senha").fill(GTN_PASS)

    log("➡️ Clicando em Acessar...")
    page.get_by_role("button", name="Acessar").click()

    try:
        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=DEFAULT_TIMEOUT_MS)
    except Exception:
        pass

    aguardar_estabilidade(page, "pós-login")
    log(f"✅ Pós-login. URL atual: {page.url}")

    if "login" in page.url.lower():
        salvar_debug(page, "falha_login")
        raise RuntimeError(
            "O sistema permaneceu na tela de login após o acesso. "
            "Verifique credenciais, expiração de sessão ou bloqueio do APEX."
        )

    if not url_tem_sessao(page.url):
        log("ℹ️ URL sem session explícita. Tentando validar contexto da aplicação...")
        try:
            page.goto(GTN_HOME_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            aguardar_estabilidade(page, "validação da home após login")
            log(f"✅ Home validada. URL atual: {page.url}")
        except Exception as e:
            raise RuntimeError(f"Login aparentemente efetuado, mas a home não abriu corretamente: {e}")


def listar_botoes_visiveis(page: Page) -> None:
    try:
        botoes = page.locator("button:visible, a:visible")
        qtd = min(botoes.count(), 20)
        nomes = []
        for i in range(qtd):
            try:
                texto = botoes.nth(i).inner_text(timeout=500).strip()
                if not texto:
                    texto = (botoes.nth(i).get_attribute("aria-label") or "").strip()
                if not texto:
                    texto = (botoes.nth(i).get_attribute("title") or "").strip()
                if texto:
                    nomes.append(texto.replace("\n", " "))
            except Exception:
                continue
        if nomes:
            log(f"🔎 Ações/botões visíveis na tela: {nomes}")
    except Exception:
        pass


def tela_execucao_testes_ativa(page: Page) -> bool:
    """Acoes/Linhas tambem existem em Projetos e nao identificam esta tela."""
    try:
        seletor = page.locator("#R35932200234408468_saved_reports").first
        return seletor.is_visible() and seletor.is_enabled()
    except Exception:
        return False


def tentar_abrir_menu_navegacao(page: Page) -> bool:
    candidatos = [
        page.get_by_role("button", name="Navegação Principal"),
        page.locator("#t_Button_navControl"),
        page.locator("button[aria-label='Navegação Principal']"),
        page.locator("button[title='Navegação Principal']"),
        page.locator("button[aria-label*='Navegação']"),
        page.locator("button[title*='Navegação']"),
        page.locator("button.t-Button--header"),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            alvo = candidato.first
            if alvo.is_visible(timeout=2000):
                log(f"🧭 Abrindo navegação principal com seletor alternativo #{i}...")
                alvo.scroll_into_view_if_needed()
                alvo.click(timeout=5000, force=True)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    return False


def obter_link_apex_por_texto(page: Page, texto_procurado: str) -> str | None:
    """Procura links reais, incluindo menus ocultos, sem aceitar qualquer 'teste'."""
    try:
        links = page.locator("a[href]").evaluate_all(
            """elements => elements.map(a => ({
                texto: a.innerText || a.textContent || a.getAttribute('aria-label') || a.title || '',
                href: a.href || a.getAttribute('href') || ''
            }))"""
        )
        alvo = normalizar_texto_navegacao(texto_procurado)
        eh_execucao = bool(re.fullmatch(r"execucao (?:de|dos) testes?", alvo))
        origem = urlsplit(page.url)
        encontrados = []
        for item in links:
            href = (item.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            destino = urljoin(page.url, href)
            parsed = urlsplit(destino)
            if parsed.scheme not in {"http", "https"} or (
                parsed.scheme, parsed.netloc
            ) != (origem.scheme, origem.netloc):
                continue
            if parsed.username is not None or parsed.password is not None:
                continue
            texto = normalizar_texto_navegacao(item.get("texto") or "")
            if eh_execucao:
                if url_e_execucao_testes(destino):
                    encontrados.append((0, destino))
                elif re.fullmatch(r"execucao (?:de|dos) testes?", texto):
                    encontrados.append((1, destino))
            elif texto == alvo:
                encontrados.append((0, destino))
        if encontrados:
            return min(encontrados, key=lambda item: item[0])[1]
    except Exception:
        pass
    return None


def listar_links_relevantes_debug(page: Page) -> None:
    """Ajuda a diagnosticar quais links de Testes/Ocorrências existem no HTML atual."""
    try:
        links = page.evaluate(
            """() => {
                const normalizar = (v) => (v || '')
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .toLowerCase();

                return Array.from(document.querySelectorAll('a'))
                    .map(a => ({
                        texto: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.title || '').trim().replace(/\\s+/g, ' '),
                        href: a.href || a.getAttribute('href') || ''
                    }))
                    .filter(x => {
                        const combinado = normalizar(`${x.texto} ${x.href}`);
                        return combinado.includes('teste') || combinado.includes('execucao') || combinado.includes('ocorrencia');
                    })
                    .slice(0, 20);
            }"""
        )

        if links:
            resumo = []
            for item in links:
                texto = item.get('texto') or '(sem texto)'
                href = item.get('href') or '(sem href)'
                resumo.append(f"{texto} -> {href[:120]}")
            log(f"🔗 Links relevantes no HTML: {resumo}")
        else:
            log("🔗 Nenhum link relevante de teste/execução/ocorrência apareceu no HTML atual.")
    except Exception as e:
        log(f"⚠️ Não consegui listar links relevantes: {e}")


def expandir_no_arvore_por_texto(page: Page, texto: str) -> bool:
    """Expande o nó correto clicando no toggle do LI pai, não no texto do menu."""
    try:
        resultado = page.evaluate(
            """(textoAlvo) => {
                const normalizar = (v) => (v || '')
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .toLowerCase()
                    .replace(/\\s+/g, ' ')
                    .trim();

                const alvo = normalizar(textoAlvo);
                const elementos = Array.from(document.querySelectorAll('li, a, span, div'));

                for (const el of elementos) {
                    const texto = normalizar(el.innerText || el.textContent || el.getAttribute('aria-label') || el.title || '');
                    if (!texto || !texto.includes(alvo)) continue;

                    const li = el.closest('li');
                    if (!li) continue;

                    const expanded = li.getAttribute('aria-expanded');
                    if (expanded === 'true') return 'ja_expandido';

                    const toggle = li.querySelector('.a-TreeView-toggle, button[aria-expanded], .a-TreeView-toggleIcon');
                    if (toggle) {
                        toggle.click();
                        return 'toggle_clicado';
                    }
                }

                return '';
            }""",
            texto,
        )

        if resultado:
            log(f"🌲 Nó '{texto}' tratado via JS: {resultado}")
            page.wait_for_timeout(1200)
            return True
    except Exception as e:
        log(f"⚠️ Falha ao expandir nó '{texto}' via JS: {e}")

    return False


def tentar_expandir_arvore(page: Page) -> None:
    """
    Expande a árvore do menu lateral sem clicar no texto do módulo.

    Observação importante:
    - Clicar em 'Gestão de Testes' pode navegar para a página do módulo.
    - O correto é clicar no toggle/ícone expansor do nó pai.
    """
    expandiu_algo = False

    for texto in ["Gestão de Testes", "Plano de Teste", "Testes"]:
        if expandir_no_arvore_por_texto(page, texto):
            expandiu_algo = True
            if tentar_abrir_execucao_testes_pelo_menu(page):
                return

    for rodada in range(1, 4):
        try:
            toggles = page.locator(".a-TreeView-toggle:visible, button[aria-expanded='false']:visible")
            qtd = toggles.count()
            log(f"🌲 Rodada {rodada}: toggles visíveis encontrados na árvore: {qtd}")

            for i in range(qtd):
                try:
                    alvo = toggles.nth(i)
                    alvo.scroll_into_view_if_needed()
                    alvo.click(timeout=3000, force=True)
                    page.wait_for_timeout(700)
                    expandiu_algo = True

                    if tentar_abrir_execucao_testes_pelo_menu(page):
                        return
                except ErroNavegacaoExecucaoTestes:
                    raise
                except Exception:
                    continue
        except ErroNavegacaoExecucaoTestes:
            raise
        except Exception:
            continue

    if expandiu_algo:
        log("✅ Expansão da árvore finalizada. Tentando localizar 'Execução de Testes'.")
    else:
        log("ℹ️ Não consegui expandir a árvore. Vou tentar localizar links diretos no HTML.")


def tentar_abrir_execucao_testes_pelo_menu(page: Page) -> bool:
    # O log do GTN confirma o alias execucao-dos-testes, com acentos na URL.
    # Um href real, mesmo em item oculto, evita clicar em 'Projetos de Testes'.
    link = obter_link_apex_por_texto(page, "Execução dos Testes")
    if link:
        log(f"🧪 Abrindo link específico da Execução de Testes: {unquote(urlsplit(link).path)}")
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        except Exception as e:
            log(f"⚠️ Não foi possível carregar o link específico: {e}")
            return False
        aguardar_execucao_testes_renderizada(page, "link real localizado no menu")
        return True

    candidatos = [
        page.get_by_role("treeitem", name=PADRAO_MENU_EXECUCAO_TESTES),
        page.get_by_role("link", name=PADRAO_MENU_EXECUCAO_TESTES),
        page.get_by_text(PADRAO_MENU_EXECUCAO_TESTES),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            quantidade = min(candidato.count(), 5)
        except Exception:
            continue
        for indice in range(quantidade):
            alvo = candidato.nth(indice)
            try:
                if not alvo.is_visible():
                    continue
                log(f"🧪 Clicando no item específico Execução de/dos Testes - seletor #{i}...")
                alvo.scroll_into_view_if_needed(timeout=3000)
                alvo.click(timeout=10000)
            except Exception as e:
                log(f"ℹ️ Item específico #{i} não pôde ser clicado: {e}")
                continue
            # Uma falha de renderizacao deve subir ao fluxo, sem cliques em outras telas.
            aguardar_execucao_testes_renderizada(page, f"item específico do menu #{i}")
            return True

    return False


def tentar_abrir_execucao_testes_por_url_amigavel(page: Page) -> bool:
    """Reconsulta links reais apos a expansao; nao monta aliases por tentativa.

    Os parametros session/cs permanecem exatamente como o GTN os forneceu
    no link da pagina de destino, sem reaproveitar um checksum de outra tela.
    """
    link = obter_link_apex_por_texto(page, "Execução dos Testes")
    if not link:
        log("ℹ️ Não há link real de Execução de Testes no HTML atual. URLs não serão adivinhadas.")
        return False
    try:
        page.goto(link, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    except Exception as e:
        log(f"⚠️ O link real de Execução de Testes não carregou: {e}")
        return False
    aguardar_execucao_testes_renderizada(page, "link real reconsultado após expansão")
    return True


def abrir_execucao_testes(page: Page) -> None:
    if tela_execucao_testes_ativa(page):
        log("✅ Tela de Execução de Testes já está ativa. Seguindo o fluxo.")
        return

    log(f"🔎 URL atual antes de abrir menu: {page.url}")

    if not url_tem_sessao(page.url):
        raise RuntimeError(
            "A URL atual não contém sessão válida do APEX. O login não ficou persistido na navegação."
        )

    aguardar_estabilidade(page, "estado atual após login")

    if tela_execucao_testes_ativa(page):
        log("✅ Tela de Execução de Testes ficou disponível sem precisar navegar de novo.")
        return

    if tentar_abrir_execucao_testes_pelo_menu(page):
        log("✅ Execução de Testes aberta pelo destino específico encontrado na página.")
        return

    menu_aberto = tentar_abrir_menu_navegacao(page)
    if not menu_aberto:
        listar_botoes_visiveis(page)
        listar_links_relevantes_debug(page)
        salvar_debug(page, "sem_menu_no_estado_atual")
        raise RuntimeError(
            "Não encontrei o botão/menu de navegação principal no estado atual da página. "
            "Não vou redirecionar para HOME sem session para não derrubar o login."
        )

    tentar_expandir_arvore(page)

    if tela_execucao_testes_ativa(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    if tentar_abrir_execucao_testes_pelo_menu(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    listar_links_relevantes_debug(page)

    if tentar_abrir_execucao_testes_por_url_amigavel(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    listar_botoes_visiveis(page)
    salvar_debug(page, "menu_sem_execucao_testes")
    raise RuntimeError(
        "Não encontrei a opção 'Execução de Testes' no menu lateral nem por links/URLs alternativas. "
        "Verifique se o usuário tem permissão nessa tela ou envie o HTML salvo para eu mapear o alias exato."
    )


def selecionar_plano_teste(page: Page, obrigatorio: bool = True) -> None:
    """Seleciona e confirma o plano pelo nome, sem depender do ID interno do GTN."""
    if not GTN_PLANO_TESTE:
        raise RuntimeError("GTN_PLANO_TESTE está vazio. Informe o nome completo do plano de teste.")

    padrao_plano = re.compile(
        r"^\s*" + r"\s+".join(re.escape(parte) for parte in GTN_PLANO_TESTE.split()) + r"\s*$",
        re.I,
    )
    seletores = [
        page.get_by_label("Plano de Teste", exact=True),
        page.locator("select").filter(
            has=page.locator("option").filter(has_text=padrao_plano)
        ),
    ]
    seletor = None
    for candidato in seletores:
        try:
            candidato.first.wait_for(state="visible", timeout=min(DEFAULT_TIMEOUT_MS, 10000))
            seletor = candidato.first
            break
        except PlaywrightTimeoutError:
            continue

    if seletor is None:
        if not obrigatorio:
            log("ℹ️ Tela sem o campo 'Plano de Teste'; mantendo os filtros próprios de Ocorrências.")
            return
        salvar_debug(page, "campo_plano_teste_ausente")
        raise RuntimeError("Não encontrei o campo 'Plano de Teste'. Nenhum relatório será baixado.")

    opcoes = seletor.locator("option").evaluate_all(
        "elements => elements.map(el => ({nome: el.label, valor: el.value, desabilitada: el.disabled}))"
    )
    normalizar = lambda texto: " ".join(texto.split()).casefold()
    correspondentes = [
        opcao for opcao in opcoes
        if normalizar(opcao["nome"]) == normalizar(GTN_PLANO_TESTE)
        and not opcao["desabilitada"]
    ]
    if len(correspondentes) != 1:
        salvar_debug(page, "plano_teste_indisponivel")
        disponiveis = "; ".join(opcao["nome"] for opcao in opcoes if not opcao["desabilitada"])
        raise RuntimeError(
            f"Não encontrei uma opção única e disponível para o plano '{GTN_PLANO_TESTE}'. "
            f"Planos disponíveis: {disponiveis or '(nenhum)'}. Nenhum relatório será baixado."
        )

    plano = correspondentes[0]
    if seletor.input_value(timeout=DEFAULT_TIMEOUT_MS) != plano["valor"]:
        log(f"🎯 Selecionando plano de teste: {plano['nome']}")
        seletor.select_option(value=plano["valor"], timeout=DEFAULT_TIMEOUT_MS)
        aguardar_processamento_apex(page, "alteração do plano de teste para SIT02")
        aguardar_estabilidade(page, "seleção do plano de teste")

    valor_atual = seletor.input_value(timeout=DEFAULT_TIMEOUT_MS)
    nome_atual = seletor.locator("option:checked").inner_text(timeout=DEFAULT_TIMEOUT_MS)
    if valor_atual != plano["valor"] or normalizar(nome_atual) != normalizar(GTN_PLANO_TESTE):
        salvar_debug(page, "plano_teste_nao_confirmado")
        raise RuntimeError(
            f"O GTN não manteve o plano esperado '{GTN_PLANO_TESTE}'. "
            f"Plano atual: {nome_atual}. Nenhum relatório será baixado."
        )
    log(f"✅ Plano de teste confirmado: {nome_atual.strip()}")


def contar_linhas_csv(caminho: Path) -> int:
    with abrir_csv_com_encoding_flexivel(caminho) as entrada:
        amostra = entrada.read(4096)
        entrada.seek(0)

        try:
            dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";" if ";" in amostra else ","

        reader = csv.reader(entrada, dialect)
        try:
            next(reader)
        except StopIteration:
            return 0

        return sum(1 for linha in reader if any((col or '').strip() for col in linha))


def clicar_primeiro_que_aparecer(page: Page, tentativas: list[tuple[str, object]], descricao: str, timeout: int = 8000) -> None:
    """Clica no primeiro locator visível dentre várias alternativas.

    Uso principal: menus do APEX que mudam texto/role conforme idioma, tema,
    renderização ou estado do Interactive Report.
    """
    ultimo_erro = None

    for nome, locator_fn in tentativas:
        try:
            locator = locator_fn()
            alvo = locator.first
            alvo.wait_for(state="visible", timeout=timeout)
            try:
                alvo.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            alvo.click(timeout=timeout, force=True)
            log(f"✅ Clique efetuado em {descricao}: {nome}")
            return
        except Exception as e:
            ultimo_erro = e
            continue

    raise RuntimeError(f"Não encontrei/click no {descricao}. Último erro: {ultimo_erro}")


def listar_menu_download_debug(page: Page) -> None:
    """Lista itens visíveis quando o menu de ações não apresenta Download."""
    try:
        itens = page.locator(".a-Menu-content :visible, [role='menu'] :visible, [role='menuitem']:visible")
        qtd = min(itens.count(), 30)
        textos = []
        for i in range(qtd):
            try:
                txt = itens.nth(i).inner_text(timeout=500).strip()
                if txt:
                    textos.append(" ".join(txt.split()))
            except Exception:
                continue
        if textos:
            log(f"🔎 Itens visíveis no menu APEX: {textos}")
    except Exception:
        pass


def abrir_menu_acoes_relatorio(page: Page) -> None:
    log("📤 Abrindo menu Ações do relatório...")

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        pass

    aguardar_processamento_apex(page, "antes de abrir menu Ações")

    tentativas_menu_acoes = [
        (
            "botão Ações por role",
            lambda: page.get_by_role("button", name=re.compile(r"Ações|Actions", re.I)),
        ),
        (
            "botão Ações dentro da região R35932200234408468",
            lambda: page.locator("#R35932200234408468 button").filter(has_text=re.compile(r"Ações|Actions", re.I)),
        ),
        (
            "botão padrão APEX IRR actions",
            lambda: page.locator("#R35932200234408468 button.a-IRR-button--actions, button.a-IRR-button--actions"),
        ),
        (
            "id APEX actions_button",
            lambda: page.locator("#R35932200234408468_actions_button, button[id$='_actions_button']"),
        ),
        (
            "aria-label/title Ações",
            lambda: page.locator("button[aria-label*='Ações'], button[title*='Ações'], button[aria-label*='Actions'], button[title*='Actions']"),
        ),
    ]

    clicar_primeiro_que_aparecer(page, tentativas_menu_acoes, "menu Ações", timeout=10000)
    page.wait_for_timeout(1000)


def abrir_download_csv(page: Page) -> None:
    """Abre o modal de download CSV do APEX de forma resiliente.

    O erro que estava derrubando o fluxo acontecia porque o script procurava
    apenas o menuitem com nome exatamente 'Fazer Download'. Em algumas cargas do
    APEX esse item aparece como 'Download', demora mais, ou perde o role.
    """
    abrir_menu_acoes_relatorio(page)

    log("📄 Selecionando opção de download...")

    tentativas_download = [
        (
            "menuitem Fazer Download/Download",
            lambda: page.get_by_role("menuitem", name=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "link/botão com texto Fazer Download",
            lambda: page.locator("a:has-text('Fazer Download'), button:has-text('Fazer Download')"),
        ),
        (
            "link/botão com texto Download/Baixar",
            lambda: page.locator("a:has-text('Download'), button:has-text('Download'), a:has-text('Baixar'), button:has-text('Baixar')"),
        ),
        (
            "item APEX a-Menu contendo download",
            lambda: page.locator(".a-Menu-content a, .a-Menu-content li, [role='menuitem']").filter(has_text=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "texto Download visível",
            lambda: page.get_by_text(re.compile(r"Fazer\s+Download|^\s*Download\s*$|^\s*Baixar\s*$", re.I)),
        ),
    ]

    try:
        clicar_primeiro_que_aparecer(page, tentativas_download, "opção Fazer Download/Download", timeout=12000)
    except Exception:
        listar_menu_download_debug(page)
        salvar_debug(page, "menu_sem_fazer_download")
        raise

    page.wait_for_timeout(1400)

    # Seleciona CSV quando a tela/modal oferece escolha de formato.
    tentativas_csv = [
        (
            "option CSV",
            lambda: page.get_by_role("option", name=re.compile(r"CSV", re.I)),
        ),
        (
            "radio CSV por role",
            lambda: page.get_by_role("radio", name=re.compile(r"CSV", re.I)),
        ),
        (
            "label CSV",
            lambda: page.locator("label:has-text('CSV')"),
        ),
        (
            "input CSV",
            lambda: page.locator("input[value='CSV'], input[value='csv']"),
        ),
        (
            "texto CSV",
            lambda: page.get_by_text(re.compile(r"^\s*CSV\s*$", re.I)),
        ),
    ]

    try:
        clicar_primeiro_que_aparecer(page, tentativas_csv, "formato CSV", timeout=5000)
        log("✅ Formato CSV selecionado explicitamente.")
        page.wait_for_timeout(500)
    except Exception:
        log("ℹ️ Opção CSV não apareceu explicitamente. Seguindo com o padrão da tela.")


def clicar_botao_download_final(page: Page) -> None:
    """Clica no botão final do modal de download e deixa o expect_download capturar."""
    tentativas_botao_final = [
        (
            "botão Fazer Download/Download/Baixar por role",
            lambda: page.get_by_role("button", name=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "botão no diálogo/modal",
            lambda: page.locator(".ui-dialog button, .t-Dialog button, [role='dialog'] button").filter(has_text=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "button por texto",
            lambda: page.locator("button:has-text('Fazer Download'), button:has-text('Download'), button:has-text('Baixar')"),
        ),
        (
            "link por texto",
            lambda: page.locator("a:has-text('Fazer Download'), a:has-text('Download'), a:has-text('Baixar')"),
        ),
    ]

    clicar_primeiro_que_aparecer(page, tentativas_botao_final, "botão final de download", timeout=12000)


def fechar_modal_download_simples(page: Page) -> None:
    """Fecha o modal de download sem aplicar relatório pós-modal.

    Usado na tela de Ocorrências, porque ali não existe a mesma regra de
    select pós-modal dos relatórios de Execução de Testes.
    """
    candidatos = [
        page.get_by_role("button", name="Fechar"),
        page.get_by_role("button", name="Cancelar"),
        page.locator("button.ui-dialog-titlebar-close"),
        page.locator(".ui-dialog-titlebar-close"),
        page.locator("button.t-Dialog-closeButton"),
        page.locator("button[aria-label='Close']"),
    ]

    for candidato in candidatos:
        try:
            if candidato.first.is_visible(timeout=1500):
                candidato.first.click(timeout=3000)
                log("🪟 Janela/modal de download de ocorrências fechada.")
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        log("ℹ️ Modal de ocorrências não tinha botão claro. Tentei fechar com ESC.")
    except Exception:
        log("ℹ️ Não foi possível fechar modal de ocorrências explicitamente. Seguindo o fluxo.")


def tentar_abrir_ocorrencias_pelo_menu(page: Page) -> bool:
    candidatos = [
        page.get_by_role("treeitem", name="Ocorrências"),
        page.get_by_role("link", name="Ocorrências"),
        page.get_by_text("Ocorrências", exact=True),
        page.locator("a:has-text('Ocorrências')"),
        page.locator("span:has-text('Ocorrências')"),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            alvo = candidato.first
            if alvo.is_visible(timeout=2500):
                log(f"🐞 Entrando em Ocorrências com seletor alternativo #{i}...")
                alvo.scroll_into_view_if_needed()
                alvo.click(timeout=8000, force=True)
                aguardar_estabilidade(page, "entrada em Ocorrências")
                return True
        except Exception:
            continue

    return False


def abrir_ocorrencias(page: Page) -> None:
    log("🐞 Abrindo tela de Ocorrências...")

    if tentar_abrir_ocorrencias_pelo_menu(page):
        return

    menu_aberto = tentar_abrir_menu_navegacao(page)
    if menu_aberto:
        tentar_expandir_arvore(page)
        if tentar_abrir_ocorrencias_pelo_menu(page):
            return

    listar_botoes_visiveis(page)
    salvar_debug(page, "menu_sem_ocorrencias")
    raise RuntimeError("Não encontrei a opção 'Ocorrências' no menu lateral.")


def baixar_ocorrencias(page: Page) -> Path:
    """Baixa o CSV de Ocorrências para o output com nome fixo do dashboard."""
    abrir_ocorrencias(page)
    selecionar_plano_teste(page, obrigatorio=False)

    log("📄 Ajustando quantidade de linhas das Ocorrências para 100000...")
    linhas = page.get_by_label("Linhas", exact=True)
    linhas.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    linhas.select_option("100000")
    try:
        linhas.dispatch_event("change")
    except Exception:
        pass

    aguardar_processamento_apex(page, "ajuste de linhas em Ocorrências")
    aguardar_estabilidade(page, "ajuste de linhas em Ocorrências")

    abrir_download_csv(page)
    log("⬇️ Iniciando download do relatório de Ocorrências...")

    with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
        clicar_botao_download_final(page)

    download = download_info.value
    erro_download = download.failure()
    if erro_download:
        raise RuntimeError(f"Falha no download de Ocorrências: {erro_download}")

    destino = OUTPUT_DIR / "Ocorrencias_Consolidadas_atualizado.csv"
    download.save_as(str(destino))
    log(f"✅ Ocorrências salvas em: {destino}")

    fechar_modal_download_simples(page)
    page.wait_for_timeout(POST_DOWNLOAD_PAUSE_MS)

    try:
        linhas_ocorrencias = contar_linhas_csv(destino)
        log(f"🧮 {destino.name} -> linhas de dados: {linhas_ocorrencias}")
    except Exception as e:
        log(f"⚠️ Não consegui contar as linhas do CSV de Ocorrências: {e}")

    return destino


def abrir_csv_com_encoding_flexivel(caminho: Path):
    encodings_teste = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    ultimo_erro = None

    for encoding in encodings_teste:
        try:
            f = open(caminho, "r", newline="", encoding=encoding)
            f.read(4096)
            f.seek(0)
            log(f"🔤 Lendo {caminho.name} com encoding: {encoding}")
            return f
        except UnicodeDecodeError as e:
            ultimo_erro = e
            try:
                f.close()
            except Exception:
                pass
            continue

    raise RuntimeError(
        f"Não foi possível ler o CSV {caminho.name} com os encodings suportados. Último erro: {ultimo_erro}"
    )


def executar_fluxo() -> None:
    """Usa o contexto SIT02 validado e baixa somente o CSV de Ocorrencias."""
    validar_env()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-dev-shm-usage", "--disable-popup-blocking"],
        )
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()
        try:
            fazer_login(page)
            # Preserva a navegacao confirmada no GTN e o contexto do plano SIT02.
            # Esta passagem pela tela de testes nao baixa relatorios de cenarios.
            abrir_execucao_testes(page)
            selecionar_plano_teste(page)
            arquivo_ocorrencias = baixar_ocorrencias(page)
            log(f"🐞 Ocorrências atualizadas com sucesso: {arquivo_ocorrencias}")
        except PlaywrightTimeoutError as e:
            log(f"⏰ Timeout no download de Ocorrências: {e}")
            salvar_debug(page, "ocorrencias_timeout")
            raise
        except Exception as e:
            log(f"❌ Erro no download de Ocorrências: {e}")
            salvar_debug(page, "ocorrencias_erro")
            raise
        finally:
            try:
                context.close()
            finally:
                browser.close()


def executar() -> int:
    # O lock compartilhado tambem protege a execucao do script completo na mesma pasta.
    try:
        with LOCK_FILE.open("x", encoding="utf-8") as lock:
            lock.write(f"pid={os.getpid()} | somente_ocorrencias_sit02\n")
    except FileExistsError:
        log("⚠️ Já existe uma execução GTN em andamento nesta pasta. Encerrando sem alterar o lock.")
        return 1
    try:
        log("==================================================")
        log("🚀 SOMENTE OCORRÊNCIAS — SIT02 — V1")
        log("==================================================")
        executar_fluxo()
        log("✅ Download de Ocorrências encerrado com sucesso.")
        return 0
    except Exception as e:
        log(f"❌ Falha no download de Ocorrências: {e}")
        log(traceback.format_exc())
        return 1
    finally:
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception as e:
            log(f"⚠️ Não consegui remover o lock: {e}")


if __name__ == "__main__":
    raise SystemExit(executar())
