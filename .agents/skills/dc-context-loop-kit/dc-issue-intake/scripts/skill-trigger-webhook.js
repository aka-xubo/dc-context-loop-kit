import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const URL = 'https://gaiaworks.feishu.cn/base/automation/webhook/event/MOVFaTPEUwqYOGhd8gjcCKblngh';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SKILL_NAME = path.basename(path.resolve(__dirname, '..'));
const PROFILE_PATH = path.join(os.homedir(), '.gaia', 'skills-user-identity', 'profile.json');
const TIMEOUT_MS = Number(process.env.SKILL_TRIGGER_TIMEOUT_MS || 4000);

function parseArgs(argv) {
  const result = {};
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      positional.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (typeof next === 'string' && !next.startsWith('--')) {
      result[key] = next;
      i += 1;
    } else {
      result[key] = true;
    }
  }
  result._ = positional;
  return result;
}

const args = parseArgs(process.argv.slice(2));
const skillName = args._[0] || DEFAULT_SKILL_NAME;

function toMessage(error) {
  if (!error) return 'unknown error';
  if (typeof error.message === 'string' && error.message.trim()) return error.message;
  return String(error);
}

function getErrorCode(error) {
  if (!error) return '';
  if (typeof error.code === 'string') return error.code;
  if (error.cause && typeof error.cause.code === 'string') return error.cause.code;
  return '';
}

function isPermissionIssue(error) {
  const code = getErrorCode(error);
  return code === 'EACCES' || code === 'EPERM';
}

function normalizeNamePart(value) {
  return String(value || '').trim().replace(/\s+/g, ' ');
}

function buildDisplayName(englishName, chineseName) {
  const english = normalizeNamePart(englishName);
  const chinese = normalizeNamePart(chineseName);
  if (!english || !chinese) return '';
  return english + ' ' + chinese;
}

function printMissingUser(prefix) {
  console.log(prefix + ' 缺少使用人信息，未执行上报。');
  console.log(prefix + ' 请提供英文名和中文名，例如：英文名 abc def，中文名 张测试。');
  console.log(prefix + ' 配置命令：node ' + process.argv[1] + ' --set-user --english "abc def" --chinese "张测试"');
}

function readConfiguredUser(prefix) {
  try {
    const profile = JSON.parse(fs.readFileSync(PROFILE_PATH, 'utf8'));
    const displayName = buildDisplayName(profile.english_name, profile.chinese_name);
    if (displayName) return displayName;
  } catch (error) {
    if (error && error.code !== 'ENOENT') {
      console.log(prefix + ' 使用人信息读取失败：' + toMessage(error));
    }
  }
  printMissingUser(prefix);
  return '';
}

function writeConfiguredUser(englishName, chineseName, prefix) {
  const english = normalizeNamePart(englishName);
  const chinese = normalizeNamePart(chineseName);
  const displayName = buildDisplayName(english, chinese);
  if (!displayName) {
    printMissingUser(prefix);
    process.exitCode = 1;
    return;
  }
  fs.mkdirSync(path.dirname(PROFILE_PATH), { recursive: true });
  fs.writeFileSync(PROFILE_PATH, JSON.stringify({
    english_name: english,
    chinese_name: chinese,
    display_name: displayName,
    updated_at: new Date().toISOString(),
  }, null, 2) + '\n');
  console.log(prefix + ' 使用人信息已配置：' + displayName);
}

async function reportTrigger() {
  const prefix = '[skill-trigger-webhook]';
  if (args['set-user']) {
    writeConfiguredUser(args.english, args.chinese, prefix);
    return;
  }

  const user = readConfiguredUser(prefix);
  if (!user) return;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uuid: randomUUID(),
        skillName,
        user,
        timestamp: new Date().toISOString(),
      }),
      signal: controller.signal,
    });
    if (!response.ok) {
      console.log(prefix + ' 上报失败：HTTP ' + response.status + ' ' + response.statusText);
      return;
    }
    console.log(prefix + ' 上报成功：HTTP ' + response.status + ' ' + response.statusText);
  } catch (error) {
    const code = getErrorCode(error);
    const message = toMessage(error);
    const suffix = code ? ' (' + code + ')' : '';
    if (isPermissionIssue(error)) {
      console.log(prefix + ' 上报失败：' + message + suffix);
      console.log(prefix + ' 可能缺少网络权限，请请求提权后重试上报命令。');
      return;
    }
    console.log(prefix + ' 上报失败：' + message + suffix);
  } finally {
    clearTimeout(timer);
  }
}

void reportTrigger();
