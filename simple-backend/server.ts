import { query as agentSdkQuery } from "@anthropic-ai/claude-agent-sdk";
import { Hono, Context } from "hono";
import { serve } from "@hono/node-server";
import { cors } from "hono/cors";
import { z } from "zod";
import { execSync } from "node:child_process";
import { existsSync, statSync, readdirSync, readFileSync, lstatSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import { query as claudeCodeQuery } from "@anthropic-ai/claude-code";


const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function resolveClaudeCodePath(): string {
  const envPath = process.env.CLAUDE_CODE_VIEWER_CC_EXECUTABLE_PATH;
  if (envPath) return envPath;

  try {
    const whichResult = execSync("which claude", { encoding: "utf-8" }).trim();
    if (whichResult) return whichResult;
  } catch {
    // Continue to fallback
  }

  const projectPath = join(__dirname, "..", "node_modules", "@anthropic-ai", "claude-code", "cli.js");
  if (existsSync(projectPath)) return projectPath;

  throw new Error("Claude Code CLI not found. Please install @anthropic-ai/claude-code or set CLAUDE_CODE_VIEWER_CC_EXECUTABLE_PATH");
}

function getClaudeCodeVersion(executablePath: string): string | null {
  try {
    return execSync(`"${executablePath}" --version`, { encoding: "utf-8" }).trim();
  } catch {
    return null;
  }
}

function supportsAgentSdk(version: string | null): boolean {
  if (!version) return false;
  const match = version.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return false;
  
  const major = parseInt(match[1], 10);
  const minor = parseInt(match[2], 10);
  const patch = parseInt(match[3], 10);
  
  return major > 1 || (major === 1 && minor > 0) || (major === 1 && minor === 0 && patch >= 125);
}

// Request schema
const executeTaskSchema = z.object({
  message: z.string().min(1, "Message is required"),
  cwd: z.string().optional().default(process.cwd()),
  sessionId: z.string().optional(),
  projectId: z.string().optional(),
});

function extractTokenFromHeaders(c: Context): string | null {
  const authHeader = c.req.header("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.substring(7);
  }
  return authHeader || c.req.header("token") || c.req.header("x-token") || null;
}

async function parseRequestBody(c: Context): Promise<{ success: true; body: any } | { success: false; response: Response }> {
  try {
    const body = await c.req.json();
    if (body === null || body === undefined) {
      return { success: false, response: c.json({ success: false, error: "Request body is required" }, 400) };
    }
    return { success: true, body };
  } catch (error: any) {
    const errorMessage = error.message || "Unknown error";
    if (errorMessage.includes("JSON") || errorMessage.includes("Unexpected end") || 
        errorMessage.includes("Unexpected token") || errorMessage.includes("parse")) {
      return { success: false, response: c.json({ success: false, error: "Invalid or empty JSON in request body" }, 400) };
    }
    throw error;
  }
}

function folderToJson(folderPath: string): Record<string, { code: string; active?: boolean }> {
  const result: Record<string, { code: string; active?: boolean }> = {};
  const ignoreDirs = new Set(["node_modules", ".git", ".next", "dist", "build", ".cache", ".vscode", ".idea"]);

  function walkDir(dir: string, baseDir: string) {
    const entries = readdirSync(dir);
    
    for (const entry of entries) {
      // Skip ignored directories
      if (ignoreDirs.has(entry)) continue;
      
      const fullPath = join(dir, entry);
      const relPath = relative(baseDir, fullPath);
      
      try {
        const stat = lstatSync(fullPath);
        
        if (stat.isDirectory()) {
          walkDir(fullPath, baseDir);
        } else if (stat.isFile()) {
          // Skip binary files and large files (> 1MB)
          if (stat.size > 1024 * 1024) continue;
          
          try {
            const code = readFileSync(fullPath, "utf-8");
            result[relPath] = { code, active: true };
          } catch (error: any) {
            // Fallback for non-UTF8 files
            try {
              const code = readFileSync(fullPath, "latin1");
              result[relPath] = { code, active: true };
            } catch {
              // Skip files that can't be read
            }
          }
        }
      } catch {
        // Skip entries that can't be accessed
      }
    }
  }

  if (existsSync(folderPath) && statSync(folderPath).isDirectory()) {
    walkDir(folderPath, folderPath);
  }

  return result;
}

async function createSession(
  projectId: string,
  token: string,
  sessionId: string,
  folderData: Record<string, { code: string; active?: boolean }>
): Promise<{ success: true; sessionId: string } | { success: false; error: string }> {
  try {
    const apiUrl = `https://dev.v3api.superengineer.ai/main/project/${projectId}/create-session`;
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: "Session update",
        session_id: sessionId,
        data: folderData,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return { success: false, error: `Failed to create session: ${response.status} ${errorText}` };
    }

    const data = await response.json() as { session_id?: string };
    return { success: true, sessionId: data.session_id || sessionId };
  } catch (error: any) {
    return { success: false, error: `Error creating session: ${error.message}` };
  }
}

async function saveSessionChat(
  projectId: string,
  token: string,
  sessionId: string,
  userInput: string,
  agentResponse: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const apiUrl = `https://dev.v3api.superengineer.ai/main/project/${projectId}/save-session-chat`;
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_input: userInput,
        agent_response: agentResponse,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return { success: false, error: `Failed to save chat: ${response.status} ${errorText}` };
    }

    return { success: true };
  } catch (error: any) {
    return { success: false, error: `Error saving chat: ${error.message}` };
  }
}

// Initialize Claude Code path
let claudeCodeExecutablePath: string;
let claudeCodeVersion: string | null;
let useAgentSdk: boolean;

try {
  claudeCodeExecutablePath = resolveClaudeCodePath();
  claudeCodeVersion = getClaudeCodeVersion(claudeCodeExecutablePath);
  useAgentSdk = supportsAgentSdk(claudeCodeVersion);
} catch (error) {
  console.error("Failed to initialize Claude Code:", error);
  process.exit(1);
}

// Create Hono app
const app = new Hono();

// Enable CORS
app.use("*", cors({
  origin: "*",
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowHeaders: ["Content-Type", "Authorization", "token", "x-token"],
  exposeHeaders: ["Content-Length"],
  maxAge: 600,
  credentials: true,
}));

// Health check endpoint
app.get("/health", (c) => {
  return c.json({ 
    status: "ok",
    claudeCodeVersion,
    executablePath: claudeCodeExecutablePath,
  });
});

app.post("/execute", async (c) => {
  try {
    const token = extractTokenFromHeaders(c);
    if (!token) {
      return c.json({ success: false, error: "Token is required in headers" }, 401);
    }

    const bodyResult = await parseRequestBody(c);
    if (!bodyResult.success) {
      return bodyResult.response;
    }

    const parseResult = executeTaskSchema.safeParse(bodyResult.body);
    if (!parseResult.success) {
      return c.json({ success: false, error: "Invalid request body", details: parseResult.error.errors }, 400);
    }
    
    const { message, cwd, sessionId, projectId } = parseResult.data;

    async function* generateMessages() {
      yield {
        type: "user" as const,
        message: { role: "user" as const, content: message },
        parent_tool_use_id: null,
        session_id: sessionId || "",
      };
    }

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        const sendSSE = (event: string, data: any) => {
          const sseMessage = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
          controller.enqueue(encoder.encode(sseMessage));
        };
        
          try {
            const messages: any[] = [];
            let finalResult: any = null;
            let sessionIdFromExecution: string | undefined = sessionId;
            let userInput: string = message;
            let agentResponse: string = "";

            // Log execution start for debugging
            console.log("Starting Claude Code execution:", {
              cwd,
              sessionId,
              projectId,
              executablePath: claudeCodeExecutablePath,
              version: claudeCodeVersion,
              useAgentSdk,
              hasApiKey: !!process.env.ANTHROPIC_API_KEY,
            });

            if (!existsSync(cwd)) {
              throw new Error(`Working directory does not exist: ${cwd}`);
            }
          
          try {
            if (!statSync(cwd).isDirectory()) {
              throw new Error(`Working directory is not a directory: ${cwd}`);
            }
          } catch (err: any) {
            throw new Error(`Cannot access working directory ${cwd}: ${err.message}`);
          }

         
          const options: any = {
            pathToClaudeCodeExecutable: claudeCodeExecutablePath,
            cwd,
            systemPrompt: { type: "preset" as const, preset: "claude_code" },
            settingSources: ["user", "project", "local"],
          };
          
          if (sessionId) {
            options.resume = sessionId;
          }

          if (projectId) {
            options.projectId = projectId;
          }

          let messageIter: AsyncIterable<any>;
          try {
              messageIter = await agentSdkQuery({ prompt: generateMessages(), options });
            
          } catch (queryError: any) {
            // Enhanced error handling with more details
            let errorMessage = `Failed to start Claude Code: ${queryError.message}`;
            if (queryError.exitCode !== undefined) {
              errorMessage += ` (exit code: ${queryError.exitCode})`;
            }
            if (queryError.stderr) {
              errorMessage += `\nStderr: ${queryError.stderr}`;
            }
            if (queryError.stdout) {
              errorMessage += `\nStdout: ${queryError.stdout}`;
            }
            if (queryError.stack && process.env.NODE_ENV === "development") {
              errorMessage += `\nStack: ${queryError.stack}`;
            }
            throw new Error(errorMessage);
          }

          sendSSE("start", {
            message: message.substring(0, 100) + (message.length > 100 ? "..." : ""),
            cwd,
            sessionId,
            projectId,
          });

          for await (const msg of messageIter) {
            messages.push(msg);
            
            if (msg.type === "system" && msg.subtype === "init") {
              sessionIdFromExecution = msg.session_id;
              sendSSE("session", { sessionId: sessionIdFromExecution });
            }
            
            if (msg.type === "assistant" && msg.content) {
              agentResponse += msg.content;
            }
            
            sendSSE("message", {
              type: msg.type,
              subtype: msg.subtype,
              session_id: msg.session_id,
              content: msg.type === "assistant" ? msg.content : undefined,
              result: msg.type === "result" ? msg.result : undefined,
              fullMessage: msg,
            });
            
            if (msg.type === "result") {
              finalResult = msg;
            }
          }

          // Convert folder to JSON and create/update session
          if (projectId && sessionIdFromExecution) {
            try {
              sendSSE("session_save_start", {
                projectId,
                sessionId: sessionIdFromExecution,
                action: "Converting folder to JSON and creating session",
              });

              const folderData = folderToJson(cwd);
              const fileCount = Object.keys(folderData).length;
              
              sendSSE("session_save_progress", {
                projectId,
                sessionId: sessionIdFromExecution,
                message: `Converted ${fileCount} files to JSON, creating session...`,
                fileCount,
              });

              const sessionResult = await createSession(projectId, token, sessionIdFromExecution, folderData);
              
              sendSSE("session_save_end", {
                success: sessionResult.success,
                projectId,
                sessionId: sessionIdFromExecution,
                message: sessionResult.success 
                  ? "Session created/updated successfully" 
                  : `Failed to create session: ${sessionResult.error}`,
                error: sessionResult.success ? undefined : sessionResult.error,
                agentResponse: agentResponse,
                sessionResult: sessionResult,
              });
              
              // Save chat conversation
              if (finalResult) {
                const finalResultType = typeof finalResult;
                const finalResultContent = typeof finalResult === "string" 
                  ? finalResult 
                  : (finalResult?.result ?? finalResult?.content ?? agentResponse ?? "");
                
                sendSSE("chat_save_start", {
                  projectId,
                  sessionId: sessionIdFromExecution,
                  action: "Saving chat conversation",
                  finalResultType,
                  finalResultKeys: typeof finalResult === "object" && finalResult !== null 
                    ? Object.keys(finalResult) 
                    : undefined,
                });

                const chatResult = await saveSessionChat(
                  projectId,
                  token,
                  sessionIdFromExecution,
                  userInput,
                  finalResultContent
                );
                
                sendSSE("chat_save_end", {
                  success: chatResult.success,
                  projectId,
                  sessionId: sessionIdFromExecution,
                  message: chatResult.success 
                    ? "Chat conversation saved successfully" 
                    : `Failed to save chat: ${chatResult.error}`,
                  error: chatResult.success ? undefined : chatResult.error,
                });
              }
            } catch (error: any) {
              console.error("Error saving session:", error);
              sendSSE("session_save_end", {
                success: false,
                projectId,
                sessionId: sessionIdFromExecution,
                message: `Error saving session: ${error.message}`,
                error: error.message,
              });
            }
          }

          sendSSE("complete", {
            success: true,
            sessionId: sessionIdFromExecution,
            result: finalResult,
            messageCount: messages.length,
          });

          controller.close();

        } catch (error: any) {
          console.error("Error in Claude Code execution:", error);
          
          let errorDetails = error.message || "Unknown error";
          if (error.exitCode !== undefined) {
            errorDetails += ` (exit code: ${error.exitCode})`;
          }
          if (error.stderr) {
            errorDetails += `\nStderr: ${error.stderr}`;
          }
          if (error.stdout) {
            errorDetails += `\nStdout: ${error.stdout}`;
          }
          
          // Log additional diagnostic information
          console.error("Error details:", {
            message: error.message,
            exitCode: error.exitCode,
            stderr: error.stderr,
            stdout: error.stdout,
            executablePath: claudeCodeExecutablePath,
            version: claudeCodeVersion,
            useAgentSdk,
            hasApiKey: !!process.env.ANTHROPIC_API_KEY,
            cwd,
          });
          
          sendSSE("error", {
            success: false,
            error: errorDetails,
            exitCode: error.exitCode,
            stderr: error.stderr,
            stdout: error.stdout,
            stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
          });
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error: any) {
    console.error("Request setup error:", error);
    return c.json(
      {
        success: false,
        error: error.message || "Unknown error",
        stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
      },
      500
    );
  }
});

const port = parseInt(process.env.PORT || "7000", 10);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`Server running on http://localhost:${info.port}`);
  console.log(`Health: http://localhost:${info.port}/health`);
  console.log(`Execute: POST http://localhost:${info.port}/execute`);
});