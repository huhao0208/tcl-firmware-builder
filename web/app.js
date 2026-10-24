import {REQUEST_MARKER, issueNumber, issueURL, readStatus, validate} from './config.js';

const $ = selector => document.querySelector(selector);
const form = $('#configuration');
const pageMessage = $('#page-message');
const formError = $('#form-error');
const submit = $('#submit');
const queryForm = $('#task-form');
const query = $('#task-number');
const queryButton = $('#query-button');
const queryError = $('#query-error');
const taskResult = $('#task-result');
let catalog;
let configuration;
let previousRoot;
let opening = false;
let querySequence = 0;
let queryController;
let pollTimer;
let pollCount = 0;
const DRAFT = 'tvfw.configuration.v1';

function text(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

function message(value, tone = 'info') {
  pageMessage.textContent = value;
  pageMessage.className = `notice page-message ${tone}`;
}

function persist() {
  try { localStorage.setItem(DRAFT, JSON.stringify(configuration)); }
  catch { message('浏览器无法保存草稿，当前选择仍可提交。'); }
}

function summaryRow(label, value) {
  const row = document.createElement('div');
  row.append(text('dt', label), text('dd', value));
  return row;
}

function render() {
  form.querySelector(`[name="root"][value="${configuration.root ? 'yes' : 'no'}"]`).checked = true;
  form.querySelector(`[name="launcher"][value="${configuration.launcher}"]`).checked = true;
  form.querySelector('[name="ads"]').checked = configuration.ads;
  const remote = form.querySelector('[name="remote_key"]');
  remote.checked = configuration.remote_key;
  remote.disabled = !configuration.root || configuration.launcher !== 'aerial';
  for (const app of catalog.apps) form.querySelector(`[name="remove_apps"][value="${app.id}"]`).checked = configuration.remove_apps.includes(app.id);
  form.querySelector(`[name="install_policy"][value="${configuration.install_policy}"]`).checked = true;
  for (const id of ['launcher-group', 'components-group', 'apps-group', 'policy-group']) document.getElementById(id).disabled = !configuration.root;
  $('#toggle-apps').disabled = !configuration.root;
  $('#toggle-apps').textContent = configuration.remove_apps.length === catalog.apps.length ? '全部保留' : '全部移除入口';
  const policy = catalog.policies.find(item => item.id === configuration.install_policy).label;
  $('#summary-list').replaceChildren(
    summaryRow('底包', configuration.root ? 'V178 · Magisk 27' : '原厂 V178'),
    summaryRow('桌面', configuration.launcher === 'aerial' ? 'Aerial Workbench' : '原厂桌面'),
    summaryRow('广告管理', configuration.ads ? '包含' : '不包含'),
    summaryRow('购物键', configuration.remote_key ? '可自定义' : '保留原行为'),
    summaryRow('预装入口', configuration.remove_apps.length ? `移除 ${configuration.remove_apps.length} 项` : '全部保留'),
    summaryRow('安装策略', policy)
  );
  $('#preview-launcher').textContent = configuration.launcher === 'aerial' ? 'Aerial' : '原厂桌面';
  $('#preview-root').textContent = configuration.root ? 'MAGISK 27' : 'STOCK V178';
  const custom = configuration.root && (configuration.launcher !== 'stock' || configuration.ads || configuration.remote_key || configuration.remove_apps.length || configuration.install_policy !== 'vendor');
  $('#validation-label').textContent = custom ? '自定义组合 · 尚未实刷' : (configuration.root ? '参考 Root 镜像 · 单机历史验证' : '原厂镜像 · 摘要已核对');
  $('#continue-link').hidden = true;
  formError.textContent = '';
  persist();
}

function readForm() {
  return validate({schema: 1, device: catalog.device.id,
    root: form.querySelector('[name="root"]:checked').value === 'yes',
    launcher: form.querySelector('[name="launcher"]:checked').value,
    ads: form.querySelector('[name="ads"]').checked,
    remote_key: form.querySelector('[name="remote_key"]').checked,
    remove_apps: [...form.querySelectorAll('[name="remove_apps"]:checked')].map(input => input.value),
    install_policy: form.querySelector('[name="install_policy"]:checked').value
  }, catalog);
}

form.addEventListener('change', event => {
  if (!catalog) return;
  if (event.target.name === 'root') {
    const enabled = event.target.value === 'yes';
    if (!enabled) {
      previousRoot = structuredClone(configuration);
      configuration = {schema: 1, device: catalog.device.id, root: false, launcher: 'stock', ads: false, remote_key: false, remove_apps: [], install_policy: 'vendor'};
    } else configuration = structuredClone(previousRoot || catalog.defaults);
  } else {
    if (event.target.name === 'launcher' && event.target.value === 'stock') form.querySelector('[name="remote_key"]').checked = false;
    configuration = readForm();
  }
  render();
});

$('#toggle-apps').addEventListener('click', () => {
  configuration.remove_apps = configuration.remove_apps.length === catalog.apps.length ? [] : catalog.apps.map(app => app.id);
  configuration = validate(configuration, catalog);
  render();
});

form.addEventListener('submit', event => {
  event.preventDefault();
  if (!catalog || opening) return;
  try {
    const value = readForm();
    const url = issueURL(value, catalog);
    const continuation = $('#continue-link');
    continuation.href = url;
    continuation.hidden = false;
    opening = true;
    submit.disabled = true;
    window.open(url, '_blank', 'noopener,noreferrer');
    message('已打开 GitHub 确认页。确认提交后开始构建，任务编号可用于下方查询。', 'success');
    setTimeout(() => { opening = false; submit.disabled = false; }, 1500);
  } catch (failure) {
    formError.textContent = failure.message;
    formError.focus();
  }
});

function setQueryBusy(busy) {
  queryButton.disabled = busy;
  queryButton.textContent = busy ? '正在查询…' : '查询进度';
  taskResult.setAttribute('aria-busy', String(busy));
}

function link(label, href, className) {
  const element = text('a', label, className);
  element.href = href;
  element.target = '_blank';
  element.rel = 'noopener noreferrer';
  return element;
}

function showTask(number, status) {
  const phase = status?.phase || 'queued';
  const labels = {queued: '等待构建', building: '正在构建', ready: '构建完成', failed: '构建未完成'};
  const top = document.createElement('div');
  top.className = 'result-top';
  top.append(text('span', labels[phase], 'status-pill'), link(`任务 #${number} ↗`, `https://github.com/${catalog.repository}/issues/${number}`));
  const heading = text('h3', status?.message || '请求已提交，正在等待 GitHub 校验。');
  const details = text('p', phase === 'ready' ? '下载包含完整 IMG、配置和 SHA-256 的 ZIP。' : phase === 'failed' ? '选择仍保存在此页。可查看日志后重新提交，或联系维护者重试。' : '完成后会在这里和 GitHub 请求里显示下载入口。');
  taskResult.replaceChildren(top, heading, details);
  if (status?.run_url || status?.release_url) {
    const actions = document.createElement('div');
    actions.className = 'result-links';
    if (status.release_url) actions.append(link('下载刷机包 ZIP ↗', `${status.release_url.replace('/tag/', '/download/')}/${status.zip_file}`, 'button primary'), link('配置与校验记录 ↗', status.release_url));
    if (status.run_url) actions.append(link('查看运行日志 ↗', status.run_url));
    taskResult.append(actions);
  }
  if (phase === 'ready') {
    taskResult.append(text('p', `ZIP SHA-256：${status.zip_sha256}`, 'hash'));
    taskResult.append(text('p', status.hardware_validation === 'reference_image' ? '参考镜像只引用维护者单台同板电视的历史记录，请先核对硬件。' : '此组合尚未实刷。构建校验通过不代表电视一定能启动。', 'candidate-note'));
  }
  document.title = `任务 #${number} · ${labels[phase]} · 电视固件工坊`;
}

async function responseJSON(response) {
  if (!response.ok) {
    if (response.status === 404) throw new Error('未找到该任务，请检查编号。');
    if (response.status === 403 || response.status === 429) {
      const reset = Number(response.headers.get('x-ratelimit-reset'));
      const time = reset ? new Date(reset * 1000).toLocaleTimeString('zh-CN', {timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit'}) : null;
      throw new Error(time ? `GitHub 查询次数已用完，请在 ${time}（北京时间）后重试。` : 'GitHub 暂时限制查询，请稍后重试。');
    }
    throw new Error('GitHub 暂时无法返回状态，请重试。');
  }
  const value = await response.text();
  if (value.length > 1024 * 1024) throw new Error('任务响应过大，请在 GitHub 查看。');
  try { return JSON.parse(value); } catch { throw new Error('任务状态响应无效，请重试。'); }
}

async function loadTask(number, polling = false) {
  clearTimeout(pollTimer);
  queryController?.abort();
  queryController = new AbortController();
  const controller = queryController;
  const sequence = ++querySequence;
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 12000);
  queryError.textContent = '';
  query.removeAttribute('aria-invalid');
  setQueryBusy(true);
  try {
    const base = `https://api.github.com/repos/${catalog.repository}/issues/${number}`;
    const headers = {Accept: 'application/vnd.github+json'};
    if (!polling) {
      const issue = await responseJSON(await fetch(base, {signal: controller.signal, headers}));
      if (!issue.body?.includes(REQUEST_MARKER) || issue.pull_request) throw new Error('这不是固件构建任务，请从选配网页生成请求。');
    }
    const comments = await responseJSON(await fetch(`${base}/comments?per_page=100`, {signal: controller.signal, headers}));
    if (sequence !== querySequence) return;
    const status = readStatus(comments, catalog.repository);
    showTask(number, status);
    history.replaceState(null, '', `#task=${number}`);
    if (!status || ['queued', 'building'].includes(status.phase)) {
      if (pollCount < 10) {
        pollCount++;
        pollTimer = setTimeout(() => { if (!document.hidden) loadTask(number, true); }, 60000);
      } else queryError.textContent = '构建仍在进行，可手动查询最新状态。';
    }
  } catch (failure) {
    if (sequence !== querySequence || (failure.name === 'AbortError' && !timedOut)) return;
    queryError.textContent = timedOut ? '查询超时，已有结果和选择已保留，请重试。' : failure.name === 'TypeError' ? '网络连接失败，已有结果和选择已保留，请检查网络后重试。' : failure.message;
    query.setAttribute('aria-invalid', 'true');
  } finally {
    clearTimeout(timeout);
    controller.abort();
    if (sequence === querySequence) setQueryBusy(false);
  }
}

query.addEventListener('input', () => {
  querySequence++;
  queryController?.abort();
  clearTimeout(pollTimer);
  pollCount = 0;
  setQueryBusy(false);
  queryError.textContent = '';
  query.removeAttribute('aria-invalid');
  $('#clear-task').hidden = !query.value;
});
$('#clear-task').addEventListener('click', () => {
  query.value = '';
  query.dispatchEvent(new Event('input'));
  history.replaceState(null, '', location.pathname);
  taskResult.replaceChildren(text('div', '↓', 'empty-symbol'), text('p', '提交配置后，在这里查看进度和下载结果。'));
  document.title = '电视固件工坊 · TCL T800T11';
  query.focus();
});
queryForm.addEventListener('submit', event => {
  event.preventDefault();
  if (!catalog) return;
  try {
    const number = issueNumber(query.value);
    pollCount = 0;
    loadTask(number);
  } catch (failure) {
    queryError.textContent = failure.message;
    query.setAttribute('aria-invalid', 'true');
    query.focus();
  }
});

async function init() {
  try {
    const response = await fetch('./catalog.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error('组件清单加载失败，请刷新页面重试。');
    catalog = await response.json();
    configuration = validate(structuredClone(catalog.defaults), catalog);
    try {
      const draft = localStorage.getItem(DRAFT);
      if (draft) configuration = validate(JSON.parse(draft), catalog);
    } catch { /* Incompatible drafts never reach the build request. */ }
    for (const app of catalog.apps) {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox'; input.name = 'remove_apps'; input.value = app.id;
      label.append(input, text('span', app.label));
      $('#apps-list').append(label);
    }
    for (const policy of catalog.policies) {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'radio'; input.name = 'install_policy'; input.value = policy.id;
      label.append(input, text('span', policy.label));
      $('#policies').append(label);
    }
    render();
    $('#clear-task').disabled = false;
    submit.disabled = false;
    message('先核对主板与 V178 底包。扩展组合尚未实刷，原救砖包请另行保留。');
    const match = location.hash.match(/^#task=([1-9][0-9]{0,7})$/);
    if (match) {
      query.value = match[1];
      $('#clear-task').hidden = false;
      loadTask(issueNumber(query.value));
      $('#task').scrollIntoView({block: 'start'});
    }
  } catch (failure) { message(failure.message || '页面加载失败，请刷新后重试。', 'error'); }
}
init();
