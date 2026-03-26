import fs from "node:fs";
import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function readCustomEnv(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .reduce<Record<string, string>>((acc, line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) {
        return acc;
      }

      const separatorIndex = trimmed.indexOf("=");
      if (separatorIndex <= 0) {
        return acc;
      }

      const key = trimmed.slice(0, separatorIndex).trim();
      const rawValue = trimmed.slice(separatorIndex + 1).trim();
      const value = rawValue.replace(/^['"]|['"]$/g, "");
      acc[key] = value;
      return acc;
    }, {});
}

function readMergedEnv(mode: string): Record<string, string> {
  const baseEnv = loadEnv(mode, process.cwd(), "");
  const scraperEnv = readCustomEnv(path.resolve(process.cwd(), ".env.scraper"));
  const localEnv = readCustomEnv(path.resolve(process.cwd(), ".env.local"));
  return { ...baseEnv, ...scraperEnv, ...localEnv };
}

export default defineConfig(({ mode }) => {
  const mergedEnv = readMergedEnv(mode);
  const supabaseUrl = mergedEnv.VITE_SUPABASE_URL ?? mergedEnv.SUPABASE_URL ?? "";
  const supabaseAnonKey = mergedEnv.VITE_SUPABASE_ANON_KEY ?? mergedEnv.SUPABASE_ANON_KEY ?? "";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src")
      }
    },
    define: {
      "import.meta.env.VITE_SUPABASE_URL": JSON.stringify(supabaseUrl),
      "import.meta.env.VITE_SUPABASE_ANON_KEY": JSON.stringify(supabaseAnonKey)
    }
  };
});
