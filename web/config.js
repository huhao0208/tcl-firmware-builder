export const REQUEST_MARKER = '<!-- TVFW:1 -->';
export const STATUS_MARKER = '<!-- TVFW_STATUS:1 -->';
const fields = ['schema', 'device', 'root', 'launcher', 'ads', 'remote_key', 'remove_apps', 'install_policy'];

export function validate(value, catalog) {
  if (!value || Array.isArray(value) || typeof value !== 'object' || Object.keys(value).sort().join() !== [...fields].sort().join()) throw new Error('配置字段不完整，请重新选择。');
  if (value.schema !== 1 || value.device !== catalog.device.id) throw new Error('请选择支持的主板与底包。');
  for (const key of ['root', 'ads', 'remote_key']) if (typeof value[key] !== 'boolean') throw new Error('配置格式不正确。');
  if (!['stock', 'aerial'].includes(value.launcher) || !['vendor', 'home', 'home_adb'].includes(value.install_policy)) throw new Error('不支持的桌面或安装策略。');
  const allowed = catalog.apps.map(app => app.id);
  if (!Array.isArray(value.remove_apps) || value.remove_apps.length > allowed.length || value.remove_apps.some(id => !allowed.includes(id)) || new Set(value.remove_apps).size !== value.remove_apps.length) throw new Error('精简应用只能从列表中选择。');
  if (value.remote_key && value.launcher !== 'aerial') throw new Error('购物键配置需要 Aerial 桌面。');
  if (!value.root && (value.launcher !== 'stock' || value.ads || value.remote_key || value.remove_apps.length || value.install_policy !== 'vendor')) throw new Error('扩展组件需要 Magisk 底包。');
  return {...value, remove_apps: [...value.remove_apps].sort()};
}

export function issueURL(value, catalog) {
  const configuration = validate(value, catalog);
  const body = `${REQUEST_MARKER}\n由在线配置网页生成。确认提交后开始构建；自定义组合尚未实刷。\n\n\`\`\`json\n${JSON.stringify(configuration, null, 2)}\n\`\`\``;
  const url = new URL(`https://github.com/${catalog.repository}/issues/new`);
  url.searchParams.set('title', `[构建] ${catalog.device.name} ${catalog.device.firmware}`);
  url.searchParams.set('labels', 'build-request');
  url.searchParams.set('body', body);
  return url.href;
}

export function issueNumber(value) {
  const text = String(value).trim();
  if (!/^[1-9][0-9]{0,7}$/.test(text)) throw new Error('请输入 1–8 位任务编号，例如 7。');
  return Number(text);
}

export function readStatus(comments, repository) {
  if (!Array.isArray(comments)) throw new Error('任务状态格式不正确。');
  const trusted = comments.filter(comment => comment.user?.login === 'github-actions[bot]' && comment.body?.startsWith(STATUS_MARKER));
  for (const comment of trusted.reverse()) {
    const match = comment.body.match(/```json\s*\n([\s\S]*?)\n```/);
    if (!match) continue;
    try {
      const data = JSON.parse(match[1]);
      if (data.schema !== 1 || !['queued', 'building', 'ready', 'failed'].includes(data.phase) || typeof data.message !== 'string') continue;
      if (data.run_url && !new RegExp(`^https://github\\.com/${repository.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/actions/runs/[0-9]+$`).test(data.run_url)) continue;
      if (data.phase === 'ready') {
        if (!/^[a-f0-9]{16}$/.test(data.build_id) || !/^[a-f0-9]{64}$/.test(data.zip_sha256)) continue;
        if (data.release_url !== `https://github.com/${repository}/releases/tag/build-${data.build_id}`) continue;
        if (data.zip_file !== `TCL-T800T11-V178-${data.build_id}.zip`) continue;
      }
      return data;
    } catch { /* Ignore malformed or untrusted status blocks. */ }
  }
  return null;
}
