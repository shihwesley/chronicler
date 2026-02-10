// Subprocess bridge to the chronicler-lite Python CLI.
// Wraps init, regenerate, and status commands with timeouts and error reporting.

import { execFile } from 'child_process';
import { promisify } from 'util';
import * as vscode from 'vscode';

const execFileAsync = promisify(execFile);

export interface ChroniclerStatus {
  staleCount: number;
  totalCount: number;
}

export class PythonBridge {
  private pythonPath: string;

  constructor(pythonPath: string = 'python3') {
    this.pythonPath = pythonPath;
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
    try {
      const { stdout, stderr } = await execFileAsync(this.pythonPath, args, {
        timeout,
        maxBuffer: 4 * 1024 * 1024,
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
