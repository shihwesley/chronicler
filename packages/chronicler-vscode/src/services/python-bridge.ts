// Subprocess bridge to the chronicler-lite Python CLI.
// Wraps init, regenerate, and status commands with timeouts and error reporting.

import { execFile } from 'child_process';
import { promisify } from 'util';
import * as vscode from 'vscode';

const execFileAsync = promisify(execFile);

const PROVIDER_ENV_VARS: Record<string, string> = {
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  google: 'GOOGLE_API_KEY',
};

export interface ChroniclerStatus {
  staleCount: number;
  totalCount: number;
}

export class PythonBridge {
  private pythonPath: string;
  private secretStorage: vscode.SecretStorage;

  constructor(pythonPath: string, secretStorage: vscode.SecretStorage) {
    this.pythonPath = pythonPath;
    this.secretStorage = secretStorage;
  }

  async init(workspacePath: string): Promise<string> {
    return this.run(
      ['-m', 'chronicler_lite.cli', 'init', '--path', workspacePath],
      30_000,
    );
  }

  async regenerate(workspacePath: string): Promise<string> {
    return this.run(
      ['-m', 'chronicler_lite.cli', 'regenerate', '--path', workspacePath],
      30_000,
    );
  }

  async status(workspacePath: string): Promise<ChroniclerStatus> {
    const raw = await this.run(
      ['-m', 'chronicler_lite.cli', 'status', '--path', workspacePath, '--format', 'json'],
      10_000,
    );

    try {
      const parsed = JSON.parse(raw);
      return {
        staleCount: parsed.stale_count ?? 0,
        totalCount: parsed.total_count ?? 0,
      };
    } catch {
      throw new Error(`Failed to parse status output: ${raw}`);
    }
  }

  private async run(args: string[], timeout: number): Promise<string> {
    const env: Record<string, string | undefined> = { ...process.env };

    // Inject LLM API key from SecretStorage into subprocess environment
    const provider = vscode.workspace.getConfiguration('chronicler').get<string>('llm.provider', 'anthropic');
    const envVar = PROVIDER_ENV_VARS[provider];
    if (envVar) {
      const apiKey = await this.secretStorage.get('chronicler.llm.apiKey');
      if (apiKey) {
        env[envVar] = apiKey;
      }
    }

    try {
      const { stdout, stderr } = await execFileAsync(this.pythonPath, args, {
        timeout,
        maxBuffer: 4 * 1024 * 1024,
        env,
      });
      if (stderr?.trim()) {
        console.warn('[Chronicler CLI stderr]', stderr.trim());
      }
      return stdout.trim();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);

      if (message.includes('ENOENT')) {
        vscode.window.showErrorMessage(
          `Python not found at "${this.pythonPath}". Check the chronicler.pythonPath setting.`,
        );
      } else if (message.includes('ETIMEDOUT') || message.includes('timed out')) {
        vscode.window.showErrorMessage(
          `Chronicler CLI timed out after ${timeout / 1000}s. The operation may still be running.`,
        );
      } else {
        vscode.window.showErrorMessage(`Chronicler CLI error: ${message}`);
      }

      throw err;
    }
  }
}
