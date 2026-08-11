# baixador-youtube

Automação em Python para download sequencial e em lote de mídias MP3 e MP4 com suporte a filas e autenticação.

---

## O problema

1. **O que é:** O **baixador-youtube** é um utilitário em Python com interface gráfica/batch para download de áudios e vídeos.
2. **Qual necessidade ataca:** Facilita o download de listas de vídeos e áudios em alta qualidade sem propagandas ou limites.
3. **Por que existe:** Ferramentas online possuem limites de download, convertem áudio em baixa qualidade ou exigem captchas.
4. **Qual o objetivo:** Permitir baixar playlists inteiras e filas de links com conversão MP3/MP4 direta.

---

## Recursos

- ✅ **Download de Áudio e Vídeo:** Converte áudios para MP3 e vídeos para MP4 em alta qualidade.
- ✅ **Suporte a Filas de Download:** Processa listas de links em lote sequencialmente.
- ✅ **Autenticação:** Permite usar cookies para acessar conteúdos restritos por idade.

---

## Instalação

### Pré-requisitos
- Python 3.10 ou superior
- FFmpeg instalado no sistema

### Instalação
```bash
git clone https://github.com/caducosilva/baixador-youtube.git
cd baixador-youtube
pip install -r requirements.txt
```

---

## Como usar

Execute o utilitário pelo terminal ou dando duplo clique em `FILA.bat`:
```bash
python interface.py
```

---

## Configuração

Copie o arquivo `config.exemplo.json` para `config.json` e ajuste se necessário.

| Campo | Descrição | Padrão |
|---|---|---|
| `pasta_destino` | Diretório onde os downloads serão salvos | `./downloads` |
| `qualidade_audio` | Qualidade do bitrate MP3 | `320k` |

---

## Detalhes técnicos relevantes

- **Dependências:** Utiliza `yt-dlp` e `ffmpeg` para extração de mídia.

---

## Testes

Para testar a captura de login:
```bash
python capturar_login.py
```

---

## Problemas comuns

| Mensagem de erro | Causa provável | Solução |
|---|---|---|
| `FFmpeg not found` | FFmpeg não instalado no PATH do sistema | Instale o FFmpeg e adicione a pasta `bin` às Variáveis de Ambiente |

---

## Apoie o projeto

Se este projeto te ajudou, considere fazer uma doação via PIX:

```
f74458dc-2a36-49bd-9250-1cef4365ebb8
```

---

## Licença

[MIT](LICENSE) — Carlos Eduardo
