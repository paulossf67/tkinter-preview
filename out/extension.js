"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const path = __importStar(require("path"));
let panel;
let currentDoc;
let debounce;
let pythonCache;
let output;
function activate(context) {
    output = vscode.window.createOutputChannel('Tkinter Preview');
    context.subscriptions.push(output);
    context.subscriptions.push(vscode.commands.registerCommand('tkinter-preview.openPreview', () => openPreview(context)), vscode.commands.registerCommand('tkinter-preview.refresh', () => {
        if (currentDoc) {
            void update(context, currentDoc);
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => {
        if (!panel || e.document !== currentDoc) {
            return;
        }
        const cfg = vscode.workspace.getConfiguration('tkinterPreview');
        if (!cfg.get('liveUpdate', true)) {
            return;
        }
        if (debounce) {
            clearTimeout(debounce);
        }
        debounce = setTimeout(() => void update(context, e.document), cfg.get('debounceMs', 400));
    }), vscode.workspace.onDidSaveTextDocument((doc) => {
        if (panel && doc === currentDoc) {
            void update(context, doc);
        }
    }), vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (panel && editor?.document.languageId === 'python') {
            currentDoc = editor.document;
            void update(context, editor.document);
        }
    }), vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration('tkinterPreview.pythonPath')) {
            pythonCache = undefined;
        }
    }));
}
function deactivate() {
    if (debounce) {
        clearTimeout(debounce);
    }
}
// --- painel -----------------------------------------------------------------
async function openPreview(context) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'python') {
        vscode.window.showWarningMessage('Abra um ficheiro Python para pré-visualizar a interface Tkinter.');
        return;
    }
    currentDoc = editor.document;
    if (panel) {
        panel.reveal(vscode.ViewColumn.Two, true);
    }
    else {
        panel = vscode.window.createWebviewPanel('tkinterPreview', 'Pré-visualização Tkinter', { viewColumn: vscode.ViewColumn.Two, preserveFocus: true }, {
            enableScripts: true,
            retainContextWhenHidden: true,
            localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')],
        });
        panel.webview.html = getHtml(panel.webview, context.extensionUri);
        panel.onDidDispose(() => {
            panel = undefined;
            currentDoc = undefined;
        });
        panel.webview.onDidReceiveMessage((msg) => {
            if (msg?.command === 'reveal' && typeof msg.line === 'number' && currentDoc) {
                void revealLine(currentDoc, msg.line);
            }
        });
    }
    await update(context, currentDoc);
}
async function revealLine(doc, line) {
    const target = Math.max(0, line - 1);
    const editor = await vscode.window.showTextDocument(doc, {
        viewColumn: vscode.ViewColumn.One,
        preserveFocus: false,
    });
    const pos = new vscode.Position(target, 0);
    editor.selection = new vscode.Selection(pos, pos);
    editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenterIfOutsideViewport);
}
// --- análise ---------------------------------------------------------------
async function update(context, doc) {
    if (!panel) {
        return;
    }
    panel.title = `Tkinter: ${path.basename(doc.fileName)}`;
    const python = await resolvePython();
    if (!python) {
        panel.webview.postMessage({
            type: 'error',
            message: 'Não foi possível encontrar um interpretador Python. Defina "tkinterPreview.pythonPath" nas configurações.',
        });
        return;
    }
    const script = path.join(context.extensionPath, 'parser_tk.py');
    try {
        const json = await runParser(python, script, doc.getText(), doc.fileName);
        panel.webview.postMessage({ type: 'render', data: json, file: doc.fileName });
    }
    catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        output.appendLine(message);
        panel.webview.postMessage({ type: 'error', message });
    }
}
function runParser(python, script, source, fileName) {
    return new Promise((resolve, reject) => {
        const proc = cp.spawn(python, [script, '--stdin', fileName], {
            cwd: path.dirname(script),
        });
        let out = '';
        let err = '';
        const timer = setTimeout(() => {
            proc.kill();
            reject(new Error('A análise excedeu o tempo limite (5s).'));
        }, 5000);
        proc.stdout.on('data', (d) => (out += d.toString()));
        proc.stderr.on('data', (d) => (err += d.toString()));
        proc.on('error', (e) => {
            clearTimeout(timer);
            reject(new Error(`Falha ao executar ${python}: ${e.message}`));
        });
        proc.on('close', () => {
            clearTimeout(timer);
            if (!out.trim()) {
                reject(new Error(err.trim() || 'O analisador não devolveu dados.'));
                return;
            }
            try {
                resolve(JSON.parse(out));
            }
            catch {
                reject(new Error(`Saída inválida do analisador:\n${out}\n${err}`));
            }
        });
        proc.stdin.end(source, 'utf8');
    });
}
async function resolvePython() {
    const configured = vscode.workspace
        .getConfiguration('tkinterPreview')
        .get('pythonPath');
    if (configured && configured.trim()) {
        return configured.trim();
    }
    if (pythonCache) {
        return pythonCache;
    }
    // Interpretador selecionado na extensão oficial de Python, se existir.
    const ext = vscode.extensions.getExtension('ms-python.python');
    if (ext) {
        try {
            const api = ext.isActive ? ext.exports : await ext.activate();
            const uri = vscode.window.activeTextEditor?.document.uri;
            const env = api?.environments?.getActiveEnvironmentPath?.(uri);
            if (env?.path) {
                pythonCache = env.path;
                return pythonCache;
            }
        }
        catch {
            // ignora e cai no fallback
        }
    }
    for (const candidate of process.platform === 'win32'
        ? ['python', 'py', 'python3']
        : ['python3', 'python']) {
        if (await canRun(candidate)) {
            pythonCache = candidate;
            return candidate;
        }
    }
    return undefined;
}
function canRun(command) {
    return new Promise((resolve) => {
        const proc = cp.spawn(command, ['--version']);
        proc.on('error', () => resolve(false));
        proc.on('close', (code) => resolve(code === 0));
    });
}
// --- html ------------------------------------------------------------------
function getHtml(webview, extensionUri) {
    const media = (file) => webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', file));
    const nonce = Array.from({ length: 32 }, () => 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'.charAt(Math.floor(Math.random() * 62))).join('');
    return `<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="${media('preview.css')}" />
  <title>Pré-visualização Tkinter</title>
</head>
<body>
  <div id="toolbar">
    <span id="status">A analisar…</span>
  </div>
  <div id="stage"></div>
  <script nonce="${nonce}" src="${media('preview.js')}"></script>
</body>
</html>`;
}
//# sourceMappingURL=extension.js.map