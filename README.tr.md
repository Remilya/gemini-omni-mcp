<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP v2.1

**Hepsi Bir Arada Google GenAI Multimodal, Decisions, Analyze & Canlı Dokümantasyon MCP Sunucusu**

*Canlı Docs Puller · Gemini 4 (`Carbon`, `Neon`, `Hydrogen`) & Gemma 4 · YouTube/PDF Analyze · 48 Saatlik Files API · Decisions API (`gemini-decision-1`) · Deep Research · Multimodal Embeddings · Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · SRT Deşifre & İfadeli TTS · Lyria 3.5 Müzik · Gerçek Zamanlı USD Bütçe Kilidi*

[English](README.md) | **Türkçe**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D3.2.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![4-IDE Plugin](https://img.shields.io/badge/Plugin-Antigravity%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-orange.svg)](#yapay-zeka-istemcilerine-ba%C4%9Flama)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Neden Ayrı CLI Yerine MCP?

Editörün yanında harici bir CLI açmak sürekli pencere değiştirmek ve çıktıları elle projeye taşımak demektir. Ayrıca Google'ın eski `google-gemini/gemini-cli` reposu artık yalnızca kurumsal Code Assist içindir ve **Gemini 4+** modelleri için optimize değildir; `gemini-api-cli` ise sürekli kabuk komutu çalıştırır.

**`gemini-omni-mcp` v2.1, Google'ın Kasım 2026 GenAI ekosistemini *ve* sıfır maliyetli Canlı Dokümantasyon Çekicisini doğrudan mevcut AI agent'ının içine (Antigravity, Claude Code, Cursor, Codex, VS Code, Claude Desktop) gömer:**

| Özellik | Ayrı CLI Penceresi | `gemini-omni-mcp` v2.1 |
| --- | --- | --- |
| **Canlı Resmi Dokümanlar** | Tarayıcı sekmesi veya ek MCP kurulumu | Dahili `gemini_search_docs` + `gemini_fetch_doc` (`gemini-api-docs-mcp.dev` + `llms.txt` yedekli) |
| **Gemini 4 & Gemma 4** | Tek seferde tek kabuk çağrısı | `gemini-4-carbon`, `gemini-4-neon`, `gemini-4-hydrogen`, `gemma-4-31b-it` + **64 paralel asenkron işçi** |
| **YouTube, PDF & Files API** | Her komutta tekrar bayrak girmek gerekir | `gemini_analyze` (YouTube URL, PDF, video, kod) + `gemini_files` (48 saatlik upload/list/get/delete) |
| **Sıfır Token'lı Karar Motoru** | Yavaş metin üretimi + kırılgan JSON ayrıştırma | `gemini_decide` (`client.decisions.create`) ile 1.000 `noul`/`choice`/`score` sorusu (0 çıktı token'ı) |
| **Multimodal Çıktılar** | Çıktıları elle kopyalama | PNG, MP4, WAV/MP3, `.srt`/`.md`/`.json` transkriptler, raporlar ve contact sheet doğrudan diske yazılır |
| **Maliyet Güvenliği** | Otomatik USD harcama kesicisi yok | Canlı harcama defteri + otomatik `OMNI_HARD_STOP_LIMIT_USD` bütçe kilidi |

---

## Araç Matrisi (18 Araç: 15 Çekirdek + 3 Opsiyonel 3D/CAD)

### Çekirdek Araçlar (Her Zaman Aktif)

| Kategori | Araç | Model(ler) / Kaynak | Yetenekler |
| --- | --- | --- | --- |
| **Canlı Docs** | `gemini_search_docs` | `gemini-api-docs-mcp.dev` + `llms.txt` | Resmi Gemini API ve SDK dokümanlarını `language`, `scope`, `source`, `api` filtreleriyle canlı arar (\$0.00) |
| **Canlı Docs** | `gemini_fetch_doc` | `gemini-api-docs-mcp.dev` + `aistudio.google.com` | `chunk_id` parçalarını veya izinli HTTPS `.md` sayfalarını temiz Markdown olarak çeker (\$0.00) |
| **Analiz** | `gemini_analyze` | `gemini-4-hydrogen`, `gemini-4-neon`, `gemini-4-carbon` | Tek çağrıda PDF, görsel, ses, video, kod/CSV, `files/<id>` URI'leri ve **YouTube URL** analizi (JSON Schema + Google Search opsiyonel) |
| **Files API** | `gemini_files` | Gemini Files API (48 saat) | Büyük video/PDF dosyalarını bir kez `upload` (aktif bekleme dahil), `list`, `get`, `delete` ile yönetir |
| **Decisions** | `gemini_decide` | `gemini-decision-1` | Metin, PDF, ses, görsel ve video üzerinde tek ileri geçişle `noul` (evet/hayır), `choice` ve `score` olasılıkları (0 çıktı token'ı) |
| **Agents** | `gemini_deep_research` | `deep-research-preview-04-2026`, `deep-research-max-preview-04-2026`, `antigravity-preview-09-2026` | Arka planda çok adımlı araştırma `start`, `status`, `run_and_wait`, `cancel` ve `delete` + Markdown kayıt |
| **Embeddings** | `gemini_embed` | `gemini-embedding-2` | Metin, görsel, ses, video ve PDF için birleşik multimodal vektörler + ikili kosinüs benzerlik matrisi |
| **Görsel** | `gemini_image_fusion` | `gemini-nano-banana-2.1`, `gemini-3.1-flash-image`, `gemini-3-pro-image` | 14 adede kadar referans + stil çıpası birleştirme, karakter/mimari/sprite ön ayarları, `0.5K`–`4K` `ImageConfig` |
| **Görsel** | `gemini_image_edit` | `gemini-nano-banana-2.1` | Bölgesel düzenleme, maskeli `inpaint`/`outpaint` ve `2x`/`4x` AI yükseltme (Lanczos yedekli; kapatılan Imagen'in yerini alır) |
| **Video** | `gemini_video_studio` | `gemini-omni-1.2-flash`, `gemini-omni-1.1-flash` | `3s`–`15s` video üretimi, `extend`, `edit`, `seamless_loop`, kareler arası geçiş, `1080p`/`4k` için otomatik URI indirme |
| **Ses & STT** | `gemini_audio_studio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, `lyria-3.5` | İfadeli TTS (`speech_metadata`), ses/video deşifresi (`text`, `md`, `json`, `.srt` altyazı, konuşmacı ayrımı, `smart`, `custom_vocabulary`), Voices API ve Lyria 3.5 |
| **Önbellek** | `gemini_context_cache` | `gemini-4-carbon`, `gemini-4-hydrogen`, Gemini 3.x | Gemini 4 için deterministik implicit önbellek demeti (%95 indirim) + 3.x modelleri için açık `client.caches.create` |
| **Swarm** | `gemini_async_swarm` | `gemini-4-hydrogen`, `gemini-4-neon`, `gemini-4-carbon` | `thinking_level` (`minimal`..`xhigh`), Code Execution, Google Search ve JSON Schema ile 64 paralel asenkron işçi |
| **Görsel QA** | `gemini_curate_refs` | `gemini-4-hydrogen` | Numaralı Pillow JPEG contact sheet oluşturur ve en net `top_k` referansı tek seferde seçer |
| **FinOps & Modeller** | `gemini_cost_and_budget` | Çevrimdışı FinOps + Canlı API | Canlı `summary`, 26 modelli `pricing_table` (Gemma 4 dahil), `live_models` (`client.models.list`/`get`), `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` |

### Opsiyonel 3D / CAD RLAIF Paketi (Varsayılan Açık; İsteğe Bağlı Kapatılabilir)

Yalnızca **15 çekirdek araçla** hafif modda çalıştırmak için `GEMINI_OMNI_ENABLE_3D_TOOLS=false` ayarlayın veya `--no-3d-tools` kullanın.

| Araç | Birincil Model(ler) | Yetenekler |
| --- | --- | --- |
| `vision_extract_3d_spec` | `gemini-4-hydrogen` + PIL | Piksel medyanı HEX örnekleme + yapısal PBR malzeme paleti, 3D oranlar ve üçgen bütçesi spesifikasyonu |
| `vision_rlaif_3d_critic` | `gemini-4-hydrogen` | Çok açılı 3D render'ları referanslar ve `spec_rules` ile kıyaslayarak koordinat/mesh düzeltmeleri üretir |
| `gemini_3d_judge_and_autopatch` | `gemini-4-carbon` + `gemini-4-hydrogen` | Üst düzey 3D görsel ve kod denetçisi; `.py` scriptlerini `ast.parse` kontrolüyle yamalar, Blender/özel render çalıştırır, hatada geri sarar ve 5 denemede devreyi keser |

---

## Canlı Docs Puller & Resmi Google Agent Kurulumu

`gemini-omni-mcp`, canlı dokümantasyon arama (`gemini_search_docs`) ve sayfa çekme (`gemini_fetch_doc`) araçlarını **API anahtarı gerektirmeden** ve `https://aistudio.google.com/llms.txt` yedeğiyle birlikte doğrudan MCP sunucusunun içine entegre eder.

İsterseniz Google'ın bağımsız resmi araçlarını da yanına kurabilirsiniz:

```bash
# Bağımsız resmi Gemini Docs MCP sunucusu
npx add-mcp "https://gemini-api-docs-mcp.dev"

# Resmi Gemini API agent yetenekleri (güncel SDK sözdizimi ve kurallar)
npx skills add google-gemini/gemini-skills --skill gemini-api-dev

# Antigravity'de tek komutla eklenti kurulumu
agy plugin install https://github.com/google-gemini/gemini-skills

# Terminalden doğrudan Gemini API çağıran bağımsız Go CLI
curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash
```

---

## Hızlı Kurulum & Yapay Zeka İstemcilerine Bağlama

Bu repo tüm büyük agent ekosistemleri için yerel eklenti manifestlerini (`plugin.json` Antigravity, `.claude-plugin/plugin.json` Claude Code, `.cursor-plugin/plugin.json` Cursor, `.codex-plugin/plugin.json` Codex) `mcp_config.json` ve `skills/gemini-omni/SKILL.md` ile birlikte içerir.

```bash
# Doğrudan GitHub üzerinden uvx ile çalıştır
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp

# Veya yerel klondan çalıştır
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv run gemini-omni-mcp --list-tools
```

<details open>
<summary><strong>Antigravity / Claude Code / Cursor / Codex / VS Code Örnekleri</strong></summary>

```json
{
  "mcpServers": {
    "gemini-omni": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Remilya/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "GEMINI_API_ANAHTARINIZ",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0",
        "GEMINI_OMNI_ENABLE_3D_TOOLS": "true"
      }
    }
  }
}
```

Claude Code CLI:
```bash
claude mcp add gemini-omni \
  -e GEMINI_API_KEY="GEMINI_API_ANAHTARINIZ" \
  -e OMNI_HARD_STOP_LIMIT_USD="50.0" \
  -- uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp
```

</details>

---

## Gerçek Zamanlı USD Harcama Takibi & Bütçe Kilidi

Tüm token, görsel, video, ses ve önbellek kullanımları `<workspace>/.gemini-omni/usage_ledger.json` dosyasına yazılır:

- **Varsayılan limit:** `$50.00 USD` (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Otomatik devre kesici:** Limit aşıldığında defter kilitlenir, bellek içi API anahtarları silinir ve `HardBudgetStopError` fırlatılır.
- **Araç komutları:** `summary`, `live_models`, `estimate_batch`, `set_budget_limit` (`0` verilirse kilidi kapatır), `reset_ledger`.

---

## Geliştirme & Testler

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync --extra dev

# Çevrimdışı birim testleri (API anahtarı gerekmez)
uv run --extra dev pytest -v

# Kayıtlı araçları kontrol et
uv run gemini-omni-mcp --list-tools
```

---

## Lisans

MIT Lisansı — [LICENSE](LICENSE).
