const AUTH_CONFIG = {
  usuarios: [
    {
      usuario: "conecta",
      senha: "ti@2026"
    },
    {
      usuario: "igor.longo",
      senha: "log@2026"
    }
  ],
  chaveAuth: "dashboard_auth"
};

function jaAutenticado() {
  return sessionStorage.getItem(AUTH_CONFIG.chaveAuth) === "ok";
}

function fazerLogin(usuario, senha) {

  const usuarioEncontrado = AUTH_CONFIG.usuarios.find(
    u => u.usuario === usuario
  );

  if (!usuarioEncontrado) {
    return { sucesso: false, erro: "usuario" };
  }

  if (usuarioEncontrado.senha !== senha) {
    return { sucesso: false, erro: "senha" };
  }

  sessionStorage.setItem(AUTH_CONFIG.chaveAuth, "ok");
  sessionStorage.setItem("usuario_logado", usuario);

  return { sucesso: true };
}

function fazerLogout() {
  sessionStorage.removeItem(AUTH_CONFIG.chaveAuth);
  sessionStorage.removeItem("usuario_logado");
  window.location.replace("login.html");
}

function protegerPagina(destinoLogin = "login.html") {
  if (!jaAutenticado()) {
    window.location.replace(destinoLogin);
  }
}

function limparSessao() {
  sessionStorage.removeItem(AUTH_CONFIG.chaveAuth);
  sessionStorage.removeItem("usuario_logado");
}