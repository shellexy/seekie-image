'use strict';

/* ============================================================
 * 基础工具
 * ============================================================ */

const $ = (selector, root = document) => root.querySelector(selector);
const TOKEN = $('meta[name="app-token"]').content;
const APP_NAME = 'Seekie Image';
const MAX_REFS = 10;

// 图标取自 Lucide（ISC 许可），内联进来以免依赖网络。
const ICONS = {
  plus: '<path d="M5 12h14M12 5v14"/>',
  more: '<circle cx="12" cy="5" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="19" r="1.2" fill="currentColor"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
  pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  trash: '<path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2M10 11v6M14 11v6"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  sliders: '<path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  imagePlus: '<path d="M16 5h6M19 2v6M21 11.5V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7.5"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/><circle cx="9" cy="9" r="2"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4M22 5h-4M4 17v2M5 18H3"/>',
  wand: '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72M14 7l3 3M5 6v4M19 14v4M10 2v2M7 8H3M21 16h-4M11 3H9"/>',
  frame: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/>',
  gem: '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6M2 9h20"/>',
  layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  expand: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  ring: '<circle cx="12" cy="12" r="7" stroke-width="3.2"/>',
  stop: '<rect width="12" height="12" x="6" y="6" rx="2"/>',
  images: '<path d="M18 22H4a2 2 0 0 1-2-2V6"/><path d="m22 13-1.296-1.296a2.41 2.41 0 0 0-3.408 0L11 18"/><circle cx="12" cy="8" r="2"/><rect width="16" height="16" x="6" y="2" rx="2"/>',
};

function icon(name, size = 18) {
  const template = document.createElement('template');
  template.innerHTML =
    `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
    `stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
  return template.content.firstChild;
}

/** 建 DOM 节点。文字一律走文本节点，不拼 HTML。 */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'value') el.value = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

async function api(method, path, body) {
  const init = { method, headers: { 'X-Token': TOKEN } };
  if (body instanceof Blob) {
    init.body = body;
    init.headers['Content-Type'] = 'application/octet-stream';
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers['Content-Type'] = 'application/json';
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error('和本机后台的连接断了，请重新打开应用');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error((data && data.error) || `请求失败（${response.status}）`);
  return data;
}

const pad = (n) => String(n).padStart(2, '0');

function shortTime(seconds) {
  const d = new Date(seconds * 1000);
  return `${pad(d.getMonth() + 1)}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fullTime(seconds) {
  const d = new Date(seconds * 1000);
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function elapsed(sinceSeconds) {
  const total = Math.max(0, Math.floor(Date.now() / 1000 - sinceSeconds));
  return `${Math.floor(total / 60)}:${pad(total % 60)}`;
}

function toast(text, kind) {
  const el = h('div', { class: `toast ${kind || ''}` }, text);
  // 模态对话框在浏览器的顶层渲染，提示条得挂进最上面那个对话框里才不会被遮住
  const dialog = [...document.querySelectorAll('dialog[open]')].pop();
  let box = $('#toasts');
  if (dialog) {
    box = $(':scope > .toasts', dialog) || dialog.appendChild(h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite' }));
  }
  box.append(el);
  setTimeout(() => el.remove(), kind === 'error' ? 6000 : 2600);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // 个别 WebView 不开放 Clipboard API，退回老办法
    const area = h('textarea', { value: text, style: 'position:fixed;opacity:0' });
    document.body.append(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

/* ============================================================
 * 状态
 * ============================================================ */

const state = {
  native: false,
  providers: [],
  options: null,
  defaults: null,
  sessions: [],
  currentId: null,   // null 表示「新绘画」，第一次生成时由后端建会话
  messages: [],
  refs: [],          // 输入区里待用的参考图 [{file, thumb}]
  pick: { provider_id: null, model: null, style: 'none', size: 'auto', quality: 'auto', complexity: 'default', n: 1 },
};

const els = {
  sessions: $('#sessions'),
  feed: $('#feed'),
  cards: $('#cards'),
  composer: $('#composer'),
  prompt: $('#prompt'),
  refStrip: $('#ref-strip'),
  pickers: $('#pickers'),
  generate: $('#generate'),
  fileInput: $('#file-input'),
};

const provider = (id) => state.providers.find((p) => p.id === id);
const option = (group, id) => state.options[group].find((o) => o.id === id);
const currentSession = () => state.sessions.find((s) => s.id === state.currentId) || null;
let lastWindowTitle = '';

/**
 * 页面标题和桌面窗口标题：有绘画名时用「绘画名 - Seekie Image」。
 * 桌面窗口标题归后端管；浏览器模式下改 document.title 就够了。
 */
async function syncTitle() {
  const name = currentSession()?.title?.trim();
  const title = name ? `${name} - ${APP_NAME}` : APP_NAME;
  if (document.title !== title) document.title = title;
  if (!state.native || title === lastWindowTitle) return;
  try {
    const result = await api('POST', 'api/window-title', { title });
    lastWindowTitle = result.set === false ? '' : title; // 页面还没载完时等 load 再试
  } catch {
    lastWindowTitle = '';
  }
}

/** 设置变动后，保证当前选中的服务商和模型仍然存在。 */
function fixPick() {
  const current = provider(state.pick.provider_id);
  if (current && current.models.includes(state.pick.model)) return;
  const fallback = (current && current.models.length ? current : null) ||
    state.providers.find((p) => p.models.length);
  state.pick.provider_id = fallback ? fallback.id : null;
  state.pick.model = fallback ? fallback.models[0] : null;
}

/* ============================================================
 * 弹出菜单
 * ============================================================ */

let openedMenu = null;

function closeMenu(refocus) {
  if (!openedMenu) return;
  const { menu, anchor, cleanup } = openedMenu;
  openedMenu = null;
  cleanup();
  menu.remove();
  if (anchor.hasAttribute('aria-expanded')) anchor.setAttribute('aria-expanded', 'false');
  if (refocus) anchor.focus();
}

/**
 * items: { label, hint?, icon?, checked?, danger?, disabled?, onSelect } | { group } | { separator: true }
 * 带 checked 字段的项按单选渲染。
 * 传 at: {x, y} 时当作右键菜单，在鼠标位置弹出；anchor 只用来在关闭后把焦点还回去。
 */
function openMenu(anchor, items, { align = 'start', at = null } = {}) {
  if (!at && openedMenu && openedMenu.anchor === anchor) return closeMenu(true);
  closeMenu(false);

  const menu = h('div', { class: 'menu', role: 'menu', tabindex: '-1' });
  for (const item of items) {
    if (item.group) {
      menu.append(h('div', { class: 'menu-group' }, item.group));
    } else if (item.separator) {
      menu.append(h('div', { class: 'menu-sep', role: 'separator' }));
    } else {
      const radio = item.checked !== undefined;
      menu.append(h('button', {
        type: 'button',
        class: `menu-item ${item.danger ? 'danger' : ''}`,
        role: radio ? 'menuitemradio' : 'menuitem',
        'aria-checked': radio ? String(item.checked) : null,
        disabled: Boolean(item.disabled),
        onclick: () => { closeMenu(true); item.onSelect(); },
      },
        radio ? h('span', { class: 'menu-mark' }, item.checked && icon('check', 16)) : (item.icon && icon(item.icon, 16)),
        h('span', { class: 'menu-label' }, item.label),
        item.hint && h('span', { class: 'menu-hint' }, item.hint),
      ));
    }
  }

  // 在模态对话框里打开时要挂到对话框内部，否则会被顶层遮住
  (anchor.closest('dialog') || document.body).append(menu);
  if (!at) anchor.setAttribute('aria-expanded', 'true');

  const rect = at ? { left: at.x, right: at.x, top: at.y, bottom: at.y } : anchor.getBoundingClientRect();
  const gap = at ? 2 : 6, edge = 8;
  const below = innerHeight - rect.bottom - gap - edge;
  const above = rect.top - gap - edge;
  const wanted = Math.min(menu.scrollHeight + 2, 400);
  const placeAbove = wanted > below && above > below;
  const height = Math.min(wanted, placeAbove ? above : below);
  menu.style.maxHeight = `${height}px`;
  const width = menu.offsetWidth;
  const left = align === 'end' ? rect.right - width : rect.left;
  menu.style.left = `${Math.max(edge, Math.min(left, innerWidth - width - edge))}px`;
  menu.style.top = `${placeAbove ? rect.top - gap - height : rect.bottom + gap}px`;

  const entries = () => [...menu.querySelectorAll('.menu-item:not(:disabled)')];
  const onPointer = (event) => {
    if (!menu.contains(event.target) && (at || !anchor.contains(event.target))) closeMenu(false);
  };
  const onKey = (event) => {
    const list = entries();
    const index = list.indexOf(document.activeElement);
    const move = (to) => { event.preventDefault(); if (list.length) list[(to + list.length) % list.length].focus(); };
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeMenu(true); }
    else if (event.key === 'ArrowDown') move(index + 1);
    else if (event.key === 'ArrowUp') move(index <= 0 ? list.length - 1 : index - 1);
    else if (event.key === 'Home') move(0);
    else if (event.key === 'End') move(list.length - 1);
    else if (event.key === 'Tab') closeMenu(false);
  };
  const dismiss = () => closeMenu(false);
  document.addEventListener('pointerdown', onPointer, true);
  document.addEventListener('keydown', onKey, true);
  window.addEventListener('resize', dismiss);
  window.addEventListener('blur', dismiss);
  els.feed.addEventListener('scroll', dismiss);
  openedMenu = {
    menu, anchor,
    cleanup() {
      document.removeEventListener('pointerdown', onPointer, true);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('resize', dismiss);
      window.removeEventListener('blur', dismiss);
      els.feed.removeEventListener('scroll', dismiss);
    },
  };
  // 右键菜单不预先高亮第一项，焦点先放在菜单本身上，方向键照常可用
  (at ? menu : menu.querySelector('[aria-checked="true"]') || entries()[0] || menu).focus();
}

/* ============================================================
 * 右键菜单
 * ============================================================ */

// 元素 -> 生成菜单项的函数。图片、侧栏条目等在渲染时登记到这里。
const contextMenus = new WeakMap();
const MOD = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl+';
const TEXT_INPUTS = new Set(['text', 'search', 'url', 'password', 'number', 'email', 'tel']);

function isTextField(el) {
  return el instanceof HTMLTextAreaElement || (el instanceof HTMLInputElement && TEXT_INPUTS.has(el.type));
}

function insertText(field, text) {
  if (!(field instanceof HTMLTextAreaElement)) text = text.replace(/[\r\n]+/g, ' ').trim();
  field.focus();
  // execCommand 虽然过时，但只有它能让插入的内容进撤销栈
  if (document.execCommand('insertText', false, text)) return;
  try {
    field.setRangeText(text, field.selectionStart, field.selectionEnd, 'end');
  } catch {
    field.value = text; // 数字输入框不支持选区
  }
  field.dispatchEvent(new Event('input', { bubbles: true }));
}

/** 「粘贴」菜单项和 Ctrl+V 的后备路径：自己去读剪贴板。 */
async function pasteInto(field) {
  const wantImages = field === els.prompt;
  let text = '';
  let images = [];
  if (state.native) {
    // 桌面窗口里页面读不到剪贴板（见 clipboard.py），交给后台
    try {
      ({ text, images } = await api('POST', 'api/clipboard', { images: wantImages }));
    } catch (error) {
      return toast(error.message, 'error');
    }
    if (images.length) return addUploads(images);
  } else {
    try {
      const files = [];
      for (const item of await navigator.clipboard.read()) {
        const type = item.types.find((t) => /^image\/(png|jpeg|webp)$/.test(t));
        if (type && wantImages) files.push(new File([await item.getType(type)], '', { type }));
        else if (item.types.includes('text/plain')) text = await (await item.getType('text/plain')).text();
      }
      if (files.length) return attachFiles(files);
    } catch {
      return toast(`浏览器没有允许读取剪贴板，请直接按 ${MOD}V 粘贴`, 'error');
    }
  }
  if (text) insertText(field, text);
  else toast(wantImages ? '剪贴板里没有文字或图片' : '剪贴板里没有文字');
}

function editMenu(field) {
  const locked = field.readOnly || field.disabled;
  const secret = field.type === 'password';
  const selected = field.selectionStart !== field.selectionEnd; // 数字输入框两个都是 null
  const run = (command) => () => {
    field.focus();
    if (!document.execCommand(command)) toast(`这个操作没有成功，请用快捷键 ${MOD}${command === 'cut' ? 'X' : 'C'}`, 'error');
  };
  const items = [
    { label: '剪切', hint: `${MOD}X`, disabled: !selected || locked || secret, onSelect: run('cut') },
    { label: '复制', hint: `${MOD}C`, disabled: !selected || secret, onSelect: run('copy') },
    { label: '粘贴', hint: `${MOD}V`, disabled: locked, onSelect: () => pasteInto(field) },
    { separator: true },
    { label: '全选', hint: `${MOD}A`, disabled: !field.value, onSelect: () => field.select() },
  ];
  if (field === els.prompt) {
    items.push(
      { separator: true },
      { label: '添加参考图…', icon: 'imagePlus', onSelect: () => els.fileInput.click() },
    );
  }
  return items;
}

function bindContextMenus() {
  document.addEventListener('contextmenu', (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest('.menu')) return event.preventDefault();

    let anchor = event.target;
    let items = null;
    const field = event.target.closest('input, textarea');
    if (field && isTextField(field)) {
      // 浏览器里保留浏览器自己的菜单（拼写检查、输入法等都在里面）；
      // 桌面窗口里 pywebview 把原生菜单关掉了，这里补一个。
      if (!state.native) return;
      anchor = field;
      items = editMenu(field);
    } else {
      while (anchor && !contextMenus.has(anchor)) anchor = anchor.parentElement;
      if (!anchor) return;
      items = contextMenus.get(anchor)();
    }
    event.preventDefault();

    let at = { x: event.clientX, y: event.clientY };
    if (!at.x && !at.y) { // 用键盘上的菜单键触发时没有鼠标位置
      const rect = anchor.getBoundingClientRect();
      at = { x: rect.left + Math.min(24, rect.width / 2), y: rect.top + Math.min(24, rect.height / 2) };
    }
    const focusable = anchor.matches('button, input, textarea, [tabindex]') ? anchor : anchor.querySelector('button') || anchor;
    openMenu(focusable, items, { at });
  });
}

/* ============================================================
 * 小对话框
 * ============================================================ */

function showDialog(dialog) {
  document.body.append(dialog);
  dialog.addEventListener('close', () => dialog.remove());
  dialog.showModal();
  return dialog;
}

function confirmDialog({ title, body, confirm = '确定', danger = false }) {
  return new Promise((resolve) => {
    const dialog = h('dialog', { class: 'dialog-small' },
      h('h2', null, title),
      body && h('p', null, body),
      h('div', { class: 'dialog-actions' },
        h('button', { type: 'button', class: 'btn', autofocus: true, onclick: () => dialog.close() }, '取消'),
        h('button', { type: 'button', class: `btn ${danger ? 'destructive' : 'accent'}`, onclick: () => dialog.close('yes') }, confirm),
      ));
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'));
    showDialog(dialog);
  });
}

function promptDialog({ title, label, value = '', confirm = '保存' }) {
  return new Promise((resolve) => {
    const input = h('input', { type: 'text', value, maxlength: 60, 'aria-label': label, autofocus: true });
    const dialog = h('dialog', { class: 'dialog-small' },
      h('form', { method: 'dialog', onsubmit: (event) => { event.preventDefault(); dialog.close('yes'); } },
        h('h2', null, title),
        h('div', { class: 'field', style: 'margin-top:14px' }, input),
        h('div', { class: 'dialog-actions' },
          h('button', { type: 'button', class: 'btn', onclick: () => dialog.close() }, '取消'),
          h('button', { type: 'submit', class: 'btn accent' }, confirm),
        )));
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes' ? input.value.trim() : null));
    showDialog(dialog);
    input.select();
  });
}

function sizeDialog(current) {
  const [w0, h0] = /^\d+x\d+$/.test(current) ? current.split('x') : ['1536', '864'];
  return new Promise((resolve) => {
    const width = h('input', { type: 'number', value: w0, min: 64, max: 8192, step: 16, 'aria-label': '宽度（像素）', autofocus: true });
    const height = h('input', { type: 'number', value: h0, min: 64, max: 8192, step: 16, 'aria-label': '高度（像素）' });
    const error = h('p', { class: 'help error', role: 'alert' });
    const dialog = h('dialog', { class: 'dialog-small' },
      h('form', {
        method: 'dialog',
        onsubmit: (event) => {
          event.preventDefault();
          const w = Number(width.value), hh = Number(height.value);
          if (!Number.isInteger(w) || !Number.isInteger(hh) || w < 64 || hh < 64) {
            error.textContent = '宽和高都要填整数像素值。';
            return;
          }
          dialog.close(`${w}x${hh}`);
        },
      },
        h('h2', null, '自定义尺寸'),
        h('p', null, 'gpt-image-2.6 要求宽高都是 16 的倍数，宽高比在 1:3 到 3:1 之间。其它模型的限制以服务商文档为准。'),
        h('div', { class: 'size-inputs' }, width, '×', height),
        error,
        h('div', { class: 'dialog-actions' },
          h('button', { type: 'button', class: 'btn', onclick: () => dialog.close() }, '取消'),
          h('button', { type: 'submit', class: 'btn accent' }, '使用这个尺寸'),
        )));
    dialog.addEventListener('close', () => resolve(dialog.returnValue || null));
    showDialog(dialog);
    width.select();
  });
}

/* ============================================================
 * 侧栏
 * ============================================================ */

function renderSessions() {
  els.sessions.replaceChildren();
  syncTitle();
  if (!state.sessions.length) {
    els.sessions.append(h('p', { class: 'sessions-empty' }, '每次新绘画生成的图片都会留在这里'));
    return;
  }
  for (const session of state.sessions) {
    const items = () => [
      { label: '重命名', icon: 'pencil', onSelect: () => renameSession(session) },
      { label: '删除', icon: 'trash', danger: true, onSelect: () => deleteSession(session) },
    ];
    const more = h('button', {
      type: 'button', class: 'session-more', 'aria-label': `「${session.title}」的更多操作`,
      'aria-haspopup': 'menu', 'aria-expanded': 'false',
      onclick: () => openMenu(more, items(), { align: 'end' }),
    }, icon('more', 18));

    const row = h('div', { class: 'session', 'aria-current': session.id === state.currentId ? 'true' : null },
      h('button', { type: 'button', class: 'session-main', title: session.title, onclick: () => openSession(session.id) },
        h('span', { class: 'session-thumb' },
          session.thumb ? h('img', { src: `files/${session.thumb}`, alt: '', loading: 'lazy' }) : icon('image', 22)),
        h('span', { class: 'session-text' },
          h('span', { class: 'session-title' }, session.title),
          session.pending
            ? h('span', { class: 'session-time busy' }, '生成中…')
            : h('span', { class: 'session-time' }, shortTime(session.updated_at))),
      ),
      more,
    );
    contextMenus.set(row, items);
    els.sessions.append(row);
  }
}

function upsertSession(session) {
  state.sessions = [session, ...state.sessions.filter((s) => s.id !== session.id)];
}

let openToken = 0;

async function openSession(id) {
  const token = ++openToken;
  state.currentId = id;
  renderSessions();
  let messages = [];
  if (id) {
    try {
      messages = await api('GET', `api/sessions/${id}/messages`);
    } catch (error) {
      toast(error.message, 'error');
    }
  }
  if (token !== openToken) return; // 期间又点了别的绘画
  state.messages = messages;
  renderFeed();
  if (!id) els.prompt.focus();
}

async function renameSession(session) {
  const title = await promptDialog({ title: '重命名', label: '标题', value: session.title });
  if (!title || title === session.title) return;
  try {
    const updated = await api('PATCH', `api/sessions/${session.id}`, { title });
    state.sessions = state.sessions.map((s) => (s.id === updated.id ? updated : s));
    renderSessions();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteSession(session) {
  const ok = await confirmDialog({
    title: `删除「${session.title}」？`,
    body: '这组绘画里的所有记录和图片文件都会被删除，无法恢复。',
    confirm: '删除', danger: true,
  });
  if (!ok) return;
  try {
    await api('DELETE', `api/sessions/${session.id}`);
  } catch (error) {
    return toast(error.message, 'error');
  }
  state.sessions = state.sessions.filter((s) => s.id !== session.id);
  if (state.currentId === session.id) openSession(null);
  else renderSessions();
}

/* ============================================================
 * 记录卡片
 * ============================================================ */

function nearBottom() {
  return els.feed.scrollHeight - els.feed.scrollTop - els.feed.clientHeight < 120;
}

function scrollToBottom(instant) {
  els.feed.scrollTo({ top: els.feed.scrollHeight, behavior: instant ? 'instant' : 'smooth' });
}

function renderFeed() {
  els.cards.replaceChildren();
  if (!state.messages.length) {
    els.cards.append(emptyState());
    return;
  }
  for (const message of state.messages) els.cards.append(renderCard(message));
  scrollToBottom(true);
}

function emptyState() {
  if (!state.providers.some((p) => p.models.length)) {
    return h('div', { class: 'empty' },
      h('img', { class: 'empty-logo', src: 'static/logo.png', alt: '', width: 88, height: 88 }),
      h('h2', null, '先接上一个绘图接口'),
      h('p', null, '填入中转站或官方接口的地址和 API Key，就可以开始生成图片。'),
      h('button', { type: 'button', class: 'btn accent', onclick: () => openSettings() }, '添加接口'));
  }
  return h('div', { class: 'empty' },
    h('img', { class: 'empty-logo', src: 'static/logo.png', alt: '', width: 88, height: 88 }),
    h('h2', null, '想画点什么？'),
    h('p', null, '在下面描述画面，按 Enter 生成。可以粘贴或拖入图片作为参考。'));
}

function sizeRatio(message, image) {
  if (image && image.w && image.h) return image.w / image.h;
  const match = /^(\d+)x(\d+)$/.exec(message.params.size || '');
  return match ? Number(match[1]) / Number(match[2]) : 1.5;
}

function metaLine(message) {
  const p = message.params;
  const parts = [p.model, fullTime(message.created_at)];
  if (p.size && p.size !== 'auto') {
    const known = option('sizes', p.size);
    parts.push(known ? known.short : p.size.replace('x', '×'));
  }
  for (const [group, key, skip] of [['qualities', 'quality', 'auto'], ['styles', 'style', 'none'], ['complexities', 'complexity', 'default']]) {
    const known = p[key] && p[key] !== skip && option(group, p[key]);
    if (known) parts.push(key === 'complexity' ? known.short : known.label);
  }
  if (p.n > 1) parts.push(`${p.n} 张`);
  if (message.status === 'done' && message.finished_at) {
    parts.push(`用时 ${Math.max(1, Math.round(message.finished_at - message.created_at))} 秒`);
  }
  return parts.join(' · ');
}

function renderCard(message) {
  const card = h('article', { class: 'card', 'data-id': message.id });

  const prompt = h('p', { class: 'prompt clamped' }, message.prompt);
  const toggle = h('button', {
    type: 'button', class: 'prompt-toggle', hidden: true, 'aria-expanded': 'false',
    onclick: () => {
      const clamped = prompt.classList.toggle('clamped');
      toggle.textContent = clamped ? '展开全文' : '收起';
      toggle.setAttribute('aria-expanded', String(!clamped));
    },
  }, '展开全文');
  card.append(prompt, toggle);
  // 只有真的被截断了才显示「展开」
  requestAnimationFrame(() => { toggle.hidden = prompt.scrollHeight <= prompt.clientHeight + 1; });

  if (message.refs.length) {
    card.append(h('div', { class: 'card-refs' }, '参考图',
      message.refs.map((ref, index) => {
        const open = h('button', {
          type: 'button', class: 'card-ref', title: '查看大图', 'aria-label': `查看参考图 ${index + 1}`,
          onclick: () => openLightbox(ref, '参考图'),
        }, h('img', { src: `files/${ref.thumb}`, alt: '', loading: 'lazy' }));
        contextMenus.set(open, () => imageMenu(ref));
        return open;
      })));
  }
  card.append(h('p', { class: 'meta' }, metaLine(message)));

  if (message.status === 'pending') {
    const ratio = sizeRatio(message);
    const count = Math.max(1, message.params.n || 1);
    // 要几张就先摆几个占位格；流式生成的中间预览图会显示在对应的格子里
    card.append(h('div', { class: count > 1 ? 'results multi' : 'results' }, Array.from({ length: count }, (_, slot) =>
      h('div', { class: 'shot pending', 'data-slot': slot, style: `--ratio:${ratio};--h:${ratio < 1 ? 380 : 300}px` },
        h('div', { class: 'pending-label' },
          h('span', { class: 'spinner' }), '正在生成 ',
          h('span', { class: 'elapsed', 'data-since': message.created_at }, elapsed(message.created_at))),
        slot === 0 && h('button', {
          type: 'button', class: 'pill-btn small',
          title: '停止等待并断开连接。请求已经发出，服务商仍可能计费。',
          onclick: () => cancelMessage(message),
        }, icon('stop', 14), '取消')))));
    showPreviews(card, message);
    return card;
  }

  if (message.status === 'done') {
    card.append(h('div', { class: message.images.length > 1 ? 'results multi' : 'results' },
      message.images.map((image) => renderShot(message, image))));
    const asked = message.params.n || 1;
    if (message.images.length < asked) {
      card.append(h('div', { class: 'note quiet' }, icon('alert', 18),
        h('span', null, `请求了 ${asked} 张，接口只返回了 ${message.images.length} 张。有些中转站不支持一次生成多张。`)));
    }
  } else if (message.status === 'error') {
    card.append(h('div', { class: 'note error', role: 'alert' }, icon('alert', 18), h('span', null, message.error || '生成失败')));
  } else {
    card.append(h('div', { class: 'note quiet' }, icon('stop', 18), h('span', null, '已取消')));
  }

  const actions = h('div', { class: 'actions' });
  if (message.status === 'done' && message.images.length) {
    actions.append(h('button', { type: 'button', class: 'pill-btn', onclick: () => addReference(message.images[0]) },
      icon('imagePlus'), '用作参考'));
  }
  actions.append(
    h('button', { type: 'button', class: 'pill-btn', onclick: () => rerun(message) }, icon('refresh'), '再来一次'),
    h('button', { type: 'button', class: 'pill-btn', title: '把这条的提示词和参数放回输入框', onclick: () => reuse(message) },
      icon('pencil'), '改一次'),
    h('button', {
      type: 'button', class: 'pill-btn icon-only', 'aria-label': '复制提示词', title: '复制提示词',
      onclick: async () => toast((await copyText(message.prompt)) ? '提示词已复制' : '复制失败'),
    }, icon('copy')),
    h('button', {
      type: 'button', class: 'pill-btn icon-only danger', 'aria-label': '删除这条记录', title: '删除这条记录',
      onclick: () => deleteMessage(message),
    }, icon('trash')),
  );
  card.append(actions);
  return card;
}

/** 图片的操作菜单：⋮ 按钮和右键共用。 */
function imageMenu(image, { lightbox = null } = {}) {
  const leave = () => { if (lightbox) lightbox.close(); };
  return [
    !lightbox && { label: '查看大图', icon: 'expand', onSelect: () => openLightbox(image) },
    { label: '用作参考', icon: 'imagePlus', onSelect: () => { leave(); addReference(image); } },
    { label: '复制图片', icon: 'copy', onSelect: () => copyImage(image) },
    { label: '保存图片…', icon: 'download', onSelect: () => saveImage(image) },
    { label: '在文件夹中显示', icon: 'folder', onSelect: () => revealImage(image) },
  ].filter(Boolean);
}

function renderShot(message, image) {
  const ratio = sizeRatio(message, image);
  const more = h('button', {
    type: 'button', class: 'shot-more', 'aria-label': '图片操作', 'aria-haspopup': 'menu', 'aria-expanded': 'false',
    onclick: () => openMenu(more, imageMenu(image), { align: 'end' }),
  }, icon('more', 18));

  const figure = h('figure', { class: 'shot', style: `--ratio:${ratio};--h:${ratio < 1 ? 380 : 300}px` },
    h('button', { type: 'button', class: 'shot-open', 'aria-label': '查看大图', onclick: () => openLightbox(image) },
      h('img', {
        src: `files/${image.file}`, alt: `生成的图片：${message.prompt.slice(0, 60)}`, loading: 'lazy', decoding: 'async',
        onerror: (event) => {
          // 原图在用户的图片文件夹里，可能已经被移走或删掉；缩略图还在，先用它顶上
          const img = event.currentTarget;
          if (img.dataset.fallback || image.thumb === image.file) return;
          img.dataset.fallback = '1';
          img.src = `files/${image.thumb}`;
          figure.classList.add('missing');
          figure.title = '原图文件已经不在图片文件夹里了，这里显示的是缩略图';
        },
      })),
    more);
  contextMenus.set(figure, () => imageMenu(image));
  return figure;
}

/** 把流式生成的中间预览图放进对应的占位格。同一张预览图只加载一次。 */
function showPreviews(card, message) {
  for (const { slot, v } of message.previews || []) {
    const tile = card.querySelector(`.shot.pending[data-slot="${slot}"]`) || card.querySelector('.shot.pending');
    const key = `${slot}:${v}`;
    if (!tile || tile.dataset.preview === key) continue;
    tile.dataset.preview = key;
    const url = `previews/${message.id}/${slot}?v=${v}`;
    // 先在后台加载好再换上去，免得换图的瞬间闪一下空白
    const loader = new Image();
    loader.onload = () => {
      if (!tile.isConnected || tile.dataset.preview !== key) return;
      let img = tile.querySelector('img.preview');
      if (!img) {
        img = h('img', { class: 'preview', alt: '生成中的预览' });
        tile.prepend(img);
        tile.classList.add('has-preview');
      }
      img.src = url;
    };
    loader.src = url;
  }
}

function replaceCard(message) {
  const stick = nearBottom();
  state.messages = state.messages.map((m) => (m.id === message.id ? message : m));
  const old = els.cards.querySelector(`[data-id="${message.id}"]`);
  if (old) {
    const fresh = renderCard(message);
    fresh.style.animation = 'none';
    old.replaceWith(fresh);
  }
  if (stick) scrollToBottom();
}

/* ---- 卡片上的操作 ---- */

async function cancelMessage(message) {
  try {
    replaceCard(await api('POST', `api/messages/${message.id}/cancel`));
    refreshSessions();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function deleteMessage(message) {
  const ok = await confirmDialog({
    title: '删除这条记录？',
    body: message.images.length ? '生成的图片文件也会一并删除，无法恢复。' : null,
    confirm: '删除', danger: true,
  });
  if (!ok) return;
  try {
    await api('DELETE', `api/messages/${message.id}`);
  } catch (error) {
    return toast(error.message, 'error');
  }
  state.messages = state.messages.filter((m) => m.id !== message.id);
  const card = els.cards.querySelector(`[data-id="${message.id}"]`);
  if (card) card.remove();
  if (!state.messages.length) renderFeed();
  refreshSessions();
}

function rerun(message) {
  const p = message.params;
  return submit({
    session_id: message.session_id, prompt: message.prompt, refs: message.refs,
    provider_id: p.provider_id, model: p.model, style: p.style, size: p.size, quality: p.quality, complexity: p.complexity,
    n: p.n || 1,
  });
}

function reuse(message) {
  const p = message.params;
  els.prompt.value = message.prompt;
  state.refs = message.refs.slice(0, MAX_REFS);
  const source = provider(p.provider_id);
  if (source && source.models.includes(p.model)) Object.assign(state.pick, { provider_id: p.provider_id, model: p.model });
  Object.assign(state.pick, { style: p.style, size: p.size, quality: p.quality, complexity: p.complexity, n: p.n || 1 });
  renderRefs();
  renderPickers();
  syncComposer();
  els.prompt.focus();
  els.prompt.setSelectionRange(els.prompt.value.length, els.prompt.value.length);
}

function addReference(image) {
  if (/\.(svg|gif)$/i.test(image.file)) return toast('SVG 和 GIF 不能用作参考图', 'error');
  if (state.refs.some((ref) => ref.file === image.file)) return toast('这张图已经在参考图里了');
  if (state.refs.length >= MAX_REFS) return toast(`参考图最多 ${MAX_REFS} 张`, 'error');
  state.refs.push({ file: image.file, thumb: image.thumb });
  renderRefs();
  els.prompt.focus();
}

async function copyImage(image) {
  if (state.native) {
    // 桌面窗口里由后台写系统剪贴板，各个内核的 Clipboard API 在这儿都靠不住
    try {
      await api('POST', `api/files/${image.file}/copy`);
      return toast('图片已复制');
    } catch (error) {
      return toast(error.message, 'error');
    }
  }
  try {
    if (!navigator.clipboard || !window.ClipboardItem) throw new Error('unsupported');
    // 把 Promise 直接交给 ClipboardItem，WebKit 才认这是用户手势触发的
    const png = fetch(`files/${image.file}`).then((r) => r.blob()).then(toPng);
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]);
    toast('图片已复制');
  } catch {
    toast('当前环境不支持复制图片，可以用「保存图片」', 'error');
  }
}

async function toPng(blob) {
  if (blob.type === 'image/png') return blob;
  const bitmap = await createImageBitmap(blob);
  const canvas = h('canvas', { width: bitmap.width, height: bitmap.height });
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

async function saveImage(image) {
  try {
    const result = await api('POST', `api/files/${image.file}/export`);
    if (result.native) {
      if (result.saved) toast(`已保存到 ${result.saved}`);
      return;
    }
  } catch (error) {
    return toast(error.message, 'error');
  }
  // 浏览器模式：走普通下载
  const d = new Date();
  const name = `image-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}${image.file.slice(image.file.lastIndexOf('.'))}`;
  const link = h('a', { href: `files/${image.file}?download=${encodeURIComponent(name)}`, download: name });
  document.body.append(link);
  link.click();
  link.remove();
}

async function revealImage(image) {
  try {
    await api('POST', `api/files/${image.file}/reveal`);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function openLightbox(image, label = '生成的图片') {
  const dialog = h('dialog', { class: 'lightbox', 'aria-label': '查看大图' },
    h('img', { src: `files/${image.file}`, alt: label, onclick: () => dialog.close() }),
    h('div', { class: 'lightbox-bar' },
      h('button', { type: 'button', onclick: () => saveImage(image) }, icon('download', 16), '保存'),
      h('button', { type: 'button', autofocus: true, onclick: () => dialog.close() }, icon('x', 16), '关闭')));
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  contextMenus.set($('img', dialog), () => imageMenu(image, { lightbox: dialog }));
  showDialog(dialog);
}

/* ============================================================
 * 输入区
 * ============================================================ */

function renderRefs() {
  els.refStrip.hidden = !state.refs.length;
  els.refStrip.replaceChildren(...state.refs.map((ref, index) =>
    h('div', { class: 'ref-chip' },
      h('img', { src: `files/${ref.thumb}`, alt: `参考图 ${index + 1}` }),
      h('button', {
        type: 'button', 'aria-label': `移除参考图 ${index + 1}`,
        onclick: () => { state.refs.splice(index, 1); renderRefs(); },
      }, icon('x', 12)))));
}

function renderPickers() {
  const pick = state.pick;
  const pill = ({ iconName, label, set, extraClass, ariaLabel, items, onEmpty }) => {
    const button = h('button', {
      type: 'button', class: `pick ${extraClass || ''} ${set ? 'set' : ''}`,
      'aria-label': ariaLabel, 'aria-haspopup': 'menu', 'aria-expanded': 'false',
      onclick: () => (onEmpty ? onEmpty() : openMenu(button, items())),
    }, icon(iconName, 16), h('span', { class: 'pick-label' }, label), icon('chevron', 14));
    button.lastChild.classList.add('chevron');
    return button;
  };

  const choose = (key, value) => { pick[key] = value; renderPickers(); };
  const optionItems = (group, key) => () => state.options[group].map((o) => ({
    label: o.label, hint: o.hint, checked: pick[key] === o.id, onSelect: () => choose(key, o.id),
  }));

  const hasModels = state.providers.some((p) => p.models.length);
  const modelPill = pill({
    iconName: 'ring', extraClass: 'model',
    label: pick.model || '添加接口',
    ariaLabel: pick.model ? `模型：${pick.model}` : '添加接口',
    onEmpty: hasModels ? null : () => openSettings(),
    items: () => {
      const items = [];
      for (const p of state.providers) {
        if (!p.models.length) continue;
        items.push({ group: p.name });
        for (const model of p.models) {
          items.push({
            label: model, checked: pick.provider_id === p.id && pick.model === model,
            onSelect: () => { pick.provider_id = p.id; pick.model = model; renderPickers(); },
          });
        }
      }
      items.push({ separator: true }, { label: '接口设置…', icon: 'sliders', onSelect: () => openSettings() });
      return items;
    },
  });

  const style = option('styles', pick.style) || state.options.styles[0];
  const quality = option('qualities', pick.quality) || state.options.qualities[0];
  const complexity = option('complexities', pick.complexity) || state.options.complexities[0];
  const knownSize = option('sizes', pick.size);
  const count = Number(pick.n) > 1 ? Number(pick.n) : 1;

  // 重绘会换掉按钮；如果焦点原本在某个按钮上，重绘后还给同一位置的新按钮
  const focused = [...els.pickers.children].indexOf(document.activeElement);
  els.pickers.replaceChildren(
    modelPill,
    pill({
      iconName: 'wand', label: style.short, set: style.id !== 'none', ariaLabel: `风格：${style.label}`,
      items: optionItems('styles', 'style'),
    }),
    pill({
      iconName: 'frame', label: knownSize ? knownSize.short : pick.size.replace('x', '×'),
      set: pick.size !== 'auto', ariaLabel: `比例：${knownSize ? knownSize.label : pick.size}`,
      items: () => [
        ...optionItems('sizes', 'size')(),
        { separator: true },
        {
          label: '自定义尺寸…', hint: knownSize ? '' : pick.size.replace('x', '×'), checked: !knownSize,
          onSelect: async () => { const size = await sizeDialog(pick.size); if (size) choose('size', size); },
        },
      ],
    }),
    pill({
      iconName: 'gem', label: quality.short, set: quality.id !== 'auto', ariaLabel: `质量：${quality.label}`,
      items: optionItems('qualities', 'quality'),
    }),
    pill({
      iconName: 'layers', label: complexity.short, set: complexity.id !== 'default', ariaLabel: `复杂度：${complexity.label}`,
      items: optionItems('complexities', 'complexity'),
    }),
    pill({
      iconName: 'images', label: count > 1 ? `${count} 张` : '数量', set: count > 1, ariaLabel: `一次生成 ${count} 张`,
      items: optionItems('counts', 'n'),
    }),
  );
  if (focused >= 0) els.pickers.children[focused].focus();
}

function syncComposer() {
  const area = els.prompt;
  area.style.height = 'auto';
  area.style.height = `${Math.min(area.scrollHeight, 220)}px`;
  els.generate.disabled = !area.value.trim();
}

async function submit(payload) {
  let result;
  try {
    result = await api('POST', 'api/generate', payload);
  } catch (error) {
    toast(error.message, 'error');
    return false;
  }
  upsertSession(result.session);
  const sameView = payload.session_id ? payload.session_id === state.currentId : state.currentId === null;
  if (sameView) {
    const first = !state.messages.length;
    state.currentId = result.session.id;
    state.messages.push(result.message);
    if (first) els.cards.replaceChildren();
    els.cards.append(renderCard(result.message));
    scrollToBottom();
  }
  renderSessions();
  return true;
}

async function submitComposer() {
  const prompt = els.prompt.value.trim();
  if (!prompt || els.generate.dataset.busy) return;
  if (!state.pick.model) {
    toast('先添加一个绘图接口');
    return openSettings();
  }
  els.generate.dataset.busy = '1';
  const ok = await submit({ session_id: state.currentId, prompt, refs: state.refs, ...state.pick });
  delete els.generate.dataset.busy;
  if (ok) {
    els.prompt.value = '';
    state.refs = [];
    renderRefs();
    syncComposer();
  }
}

/** 把后台已经存好的图片（{file, thumb}）加进参考图。 */
function addUploads(images) {
  const room = MAX_REFS - state.refs.length;
  if (images.length > room) toast(`参考图最多 ${MAX_REFS} 张`, 'error');
  state.refs.push(...images.slice(0, Math.max(0, room)));
  renderRefs();
  els.prompt.focus();
}

async function attachFiles(files) {
  for (const file of files) {
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) {
      toast(`「${file.name || '粘贴的内容'}」不是 PNG、JPEG 或 WebP 图片`, 'error');
      continue;
    }
    if (state.refs.length >= MAX_REFS) {
      toast(`参考图最多 ${MAX_REFS} 张`, 'error');
      break;
    }
    try {
      state.refs.push(await api('POST', 'api/upload', file));
      renderRefs();
    } catch (error) {
      toast(error.message, 'error');
    }
  }
}

function bindComposer() {
  els.generate.append(icon('sparkles', 22));
  $('#attach').append(icon('imagePlus', 22));
  $('#new-session').append(icon('plus', 18), h('span', null, '新绘画'));
  $('#open-settings').append(icon('sliders', 18), h('span', null, '接口设置'));

  els.prompt.addEventListener('input', syncComposer);
  els.prompt.addEventListener('keydown', (event) => {
    // 输入法正在组字时的回车是「上屏」，不是发送
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    submitComposer();
  });
  els.composer.addEventListener('submit', (event) => { event.preventDefault(); submitComposer(); });

  $('#attach').addEventListener('click', () => els.fileInput.click());
  els.fileInput.addEventListener('change', () => { attachFiles([...els.fileInput.files]); els.fileInput.value = ''; });
  // 粘贴：图片变成参考图，文字照常进输入框。焦点不在任何输入框里时也算粘给提示词。
  document.addEventListener('paste', (event) => {
    const inPrompt = event.target === els.prompt;
    if (!inPrompt) {
      const el = event.target instanceof Element ? event.target : null;
      if ((el && el.closest('input, textarea, [contenteditable]')) || $('dialog[open]')) return;
    }
    const data = event.clipboardData;
    const files = [...(data ? data.files : [])];
    const text = data ? data.getData('text/plain') : '';
    if (files.length) {
      event.preventDefault();
      attachFiles(files);
    } else if (state.native && !text) {
      // WebKitGTK 的粘贴事件里拿不到图片，改由后台去读系统剪贴板
      event.preventDefault();
      pasteInto(els.prompt);
    } else if (!inPrompt && text) {
      event.preventDefault();
      insertText(els.prompt, text);
    }
  });

  // 监听整个窗口：文件拖到任何位置都当作参考图，也避免 WebView 把页面导航到那个文件
  const hasFiles = (event) => event.dataTransfer && [...event.dataTransfer.types].includes('Files');
  let depth = 0;
  window.addEventListener('dragenter', (event) => { if (hasFiles(event)) { depth++; els.composer.classList.add('dragging'); } });
  window.addEventListener('dragleave', (event) => { if (hasFiles(event) && --depth <= 0) { depth = 0; els.composer.classList.remove('dragging'); } });
  window.addEventListener('dragover', (event) => { if (hasFiles(event)) event.preventDefault(); });
  window.addEventListener('drop', (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    depth = 0;
    els.composer.classList.remove('dragging');
    attachFiles([...event.dataTransfer.files]);
  });

  $('#new-session').addEventListener('click', () => openSession(null));
  $('#open-settings').addEventListener('click', () => openSettings());
}

/* ============================================================
 * 接口设置
 * ============================================================ */

const IMAGE_MODEL = /image|dall|flux|imagen|seedream|banana|midjourney|stable|sd[-_x3]|kolors|ideogram|recraft/i;

function hostOf(url) {
  try {
    return new URL(/^https?:\/\//i.test(url) ? url : `https://${url}`).host;
  } catch {
    return '';
  }
}

function openSettings() {
  closeMenu(false);
  if ($('dialog.settings')) return;

  const blank = () => ({
    id: '', name: '', base_url: '', api_key: '', api_mode: 'images', timeout: state.defaults.timeout,
    modelsText: state.defaults.models.join('\n'), extraText: '', stream: false,
  });
  const draft = state.providers.map((p) => ({
    id: p.id, name: p.name, base_url: p.base_url, api_key: p.api_key, api_mode: p.api_mode, timeout: p.timeout,
    modelsText: p.models.join('\n'), stream: Boolean(p.stream),
    extraText: Object.keys(p.extra || {}).length ? JSON.stringify(p.extra, null, 2) : '',
  }));
  if (!draft.length) draft.push(blank());
  let active = Math.max(0, draft.findIndex((p) => p.id && p.id === state.pick.provider_id));
  const snapshot = () => JSON.stringify(draft);
  const initial = snapshot();
  let fieldId = 0;

  const list = h('div', { class: 'provider-list', role: 'tablist', 'aria-label': '服务商' });
  const form = h('div', { class: 'provider-form' });
  const formError = h('p', { class: 'form-error', role: 'alert' });
  const saveButton = h('button', { type: 'button', class: 'btn accent', onclick: save }, '保存');
  const dialog = h('dialog', { class: 'settings', 'aria-labelledby': 'settings-title' },
    h('div', { class: 'settings-head' },
      h('h2', { id: 'settings-title' }, '接口设置'),
      h('button', { type: 'button', class: 'icon-btn', 'aria-label': '关闭', onclick: requestClose }, icon('x', 20))),
    h('div', { class: 'settings-body' }, list, form),
    h('div', { class: 'settings-foot' },
      formError,
      h('button', { type: 'button', class: 'btn', onclick: requestClose }, '取消'),
      saveButton));

  function field(label, control, ...help) {
    const id = `settings-field-${++fieldId}`;
    control.id = id;
    return h('div', { class: 'field' }, h('label', { for: id }, label), control, ...help);
  }

  function renderList() {
    list.replaceChildren(
      ...draft.map((p, index) => h('button', {
        type: 'button', class: 'provider-tab', role: 'tab', 'aria-selected': String(index === active),
        onclick: () => { active = index; renderList(); renderForm(); },
      },
        h('strong', null, p.name.trim() || hostOf(p.base_url) || '新服务商'),
        h('span', null, hostOf(p.base_url) || '还没有填地址'))),
      h('button', {
        type: 'button', class: 'btn plain compact provider-add',
        onclick: () => { draft.push(blank()); active = draft.length - 1; renderList(); renderForm(); $('input', form).focus(); },
      }, icon('plus', 16), '添加服务商'));
  }

  function renderForm() {
    const p = draft[active];
    if (!p) {
      form.replaceChildren(h('div', { class: 'empty' },
        h('h2', null, '还没有服务商'),
        h('p', null, '点左边的「添加服务商」，填入接口地址和 API Key。')));
      return;
    }
    const bind = (key, after) => (event) => { p[key] = event.target.value; if (after) after(); };

    // 接口地址：实时显示补全后的真实请求地址
    const resolved = h('p', { class: 'help' });
    let resolveTimer = 0;
    const showResolved = () => {
      clearTimeout(resolveTimer);
      resolveTimer = setTimeout(async () => {
        if (!p.base_url.trim()) return resolved.replaceChildren('只填域名会自动补上 /v1；以 # 结尾则原样使用，不做补全。');
        try {
          const { url } = await api('POST', 'api/providers/resolve', { base_url: p.base_url, api_mode: p.api_mode });
          if (draft[active] === p && url) resolved.replaceChildren('实际请求地址：', h('code', null, url));
        } catch { /* 预览失败不影响填写 */ }
      }, 200);
    };

    const keyInput = h('input', { type: 'password', value: p.api_key, placeholder: 'sk-…', autocomplete: 'off', spellcheck: 'false', oninput: bind('api_key') });
    const keyToggle = h('button', {
      type: 'button', class: 'btn compact', 'aria-pressed': 'false',
      onclick: () => {
        const show = keyInput.type === 'password';
        keyInput.type = show ? 'text' : 'password';
        keyToggle.textContent = show ? '隐藏' : '显示';
        keyToggle.setAttribute('aria-pressed', String(show));
      },
    }, '显示');

    const modeHelp = h('p', { class: 'help' });
    const showModeHelp = () => {
      modeHelp.textContent = p.api_mode === 'chat'
        ? '部分中转站把绘图模型挂在对话接口上。这种方式只发送提示词和参考图，比例、质量、复杂度不会作为参数发送；一次多张会同时发出多次请求。'
        : '走 /images/generations，带参考图时走 /images/edits。gpt-image 系列用这个。';
      streamField.hidden = p.api_mode === 'chat';
    };
    const streamField = h('div', { class: 'field' },
      h('label', { class: 'check' },
        h('input', { type: 'checkbox', checked: p.stream, onchange: (event) => { p.stream = event.target.checked; } }),
        h('span', null, '流式生成，边画边显示预览图')),
      h('p', { class: 'help' }, '请求里会带上 ', h('code', null, '"stream": true, "partial_images": 2'),
        '，生成过程中能看到画面由模糊变清楚。中转站不认识这两个参数时会自动去掉重发；按官方计费，每张预览图多算 100 个图片输出 token。'));
    const modes = h('div', { class: 'segmented', role: 'radiogroup', 'aria-label': '接口类型' },
      [['images', 'Images API'], ['chat', 'Chat Completions']].map(([value, label]) =>
        h('label', null,
          h('input', {
            type: 'radio', name: 'api-mode', value, checked: p.api_mode === value,
            onchange: () => { p.api_mode = value; showModeHelp(); showResolved(); },
          }), label)));

    // 模型：手填，或者从 /models 拉回来点选
    const modelsArea = h('textarea', { class: 'input mono', rows: 6, value: p.modelsText, spellcheck: 'false', placeholder: '每行一个模型名', oninput: bind('modelsText', () => syncChips()) });
    const picker = h('div', { class: 'model-picker', hidden: true });
    const probeHelp = h('p', { class: 'help' }, '每行一个。模型名以服务商后台显示的为准。');
    let syncChips = () => {};
    const probeButton = h('button', {
      type: 'button', class: 'btn compact',
      onclick: async () => {
        probeButton.disabled = true;
        probeButton.textContent = '获取中…';
        probeHelp.className = 'help';
        try {
          const { models } = await api('POST', 'api/providers/probe', { base_url: p.base_url, api_key: p.api_key });
          if (draft[active] !== p) return;
          showFetchedModels(models);
        } catch (error) {
          probeHelp.className = 'help error';
          probeHelp.textContent = `获取失败：${error.message}`;
        } finally {
          probeButton.disabled = false;
          probeButton.textContent = '从接口获取';
        }
      },
    }, '从接口获取');

    function showFetchedModels(models) {
      const sorted = [...models].sort((a, b) => IMAGE_MODEL.test(b) - IMAGE_MODEL.test(a) || a.localeCompare(b));
      const filter = h('input', { type: 'search', placeholder: '筛选模型', 'aria-label': '筛选模型' });
      const chips = h('div', { class: 'model-chips' });
      const chosen = () => p.modelsText.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
      syncChips = () => {
        const selected = chosen();
        const keyword = filter.value.trim().toLowerCase();
        chips.replaceChildren(...sorted.filter((m) => m.toLowerCase().includes(keyword)).map((model) =>
          h('button', {
            type: 'button', class: 'chip', 'aria-pressed': String(selected.includes(model)),
            onclick: () => {
              const now = chosen();
              p.modelsText = (now.includes(model) ? now.filter((m) => m !== model) : [...now, model]).join('\n');
              modelsArea.value = p.modelsText;
              syncChips();
            },
          }, model)));
        if (!chips.children.length) chips.append(h('span', { class: 'help' }, '没有匹配的模型'));
      };
      filter.addEventListener('input', syncChips);
      picker.replaceChildren(filter, chips);
      picker.hidden = false;
      probeHelp.className = 'help';
      probeHelp.textContent = `接口可用，共 ${models.length} 个模型，名字像绘图模型的排在前面。点一下加入或移除。`;
      syncChips();
    }

    const extraError = h('p', { class: 'help error', role: 'alert' });
    const extraArea = h('textarea', {
      class: 'input mono', rows: 3, value: p.extraText, spellcheck: 'false', placeholder: '{"output_format": "webp"}',
      oninput: bind('extraText', () => { extraError.textContent = ''; }),
      onblur: () => { extraError.textContent = extraProblem(p) || ''; },
    });

    form.replaceChildren(
      field('名称', h('input', { type: 'text', value: p.name, placeholder: '比如：我的中转站', oninput: bind('name', renderTabsOnly) })),
      field('接口地址', h('input', {
        type: 'text', value: p.base_url, placeholder: 'https://api.example.com', spellcheck: 'false', autocomplete: 'off',
        oninput: bind('base_url', () => { renderTabsOnly(); showResolved(); }),
      }), resolved),
      field('API Key', h('div', { class: 'field-row' }, keyInput, keyToggle),
        h('p', { class: 'help' }, '以明文保存在本机的数据目录里，不会发送到接口地址以外的地方。')),
      h('div', { class: 'field' }, h('span', { class: 'label' }, '接口类型'), modes, modeHelp),
      streamField,
      field('模型', modelsArea, picker, h('div', { class: 'field-row' }, probeButton, probeHelp)),
      h('details', { class: 'advanced', open: Boolean(p.extraText.trim()) || Number(p.timeout) !== state.defaults.timeout },
        h('summary', null, '高级'),
        field('额外参数（JSON）', extraArea, extraError,
          h('p', { class: 'help' }, '会合并进每次请求体，并覆盖界面上的同名选项。例如 ',
            h('code', null, '{"output_format": "webp"}'), ' 或 ', h('code', null, '{"partial_images": 3}'), '。')),
        field('超时（秒）', h('input', { type: 'number', value: p.timeout, min: 30, max: 1800, step: 10, style: 'max-width:140px', oninput: bind('timeout') }),
          h('p', { class: 'help' }, '高质量出图可能要一两分钟。中转站自己的网关超时不受这里控制。'))),
      h('div', { class: 'form-foot' },
        h('button', {
          type: 'button', class: 'btn plain danger compact',
          onclick: () => { draft.splice(active, 1); active = Math.max(0, active - 1); renderList(); renderForm(); },
        }, icon('trash', 16), '移除这个服务商')),
    );
    // field() 给外层 div 设了 id，这里把 label 指回真正的输入框
    keyInput.id = keyInput.parentElement.id;
    keyInput.parentElement.removeAttribute('id');
    showModeHelp();
    showResolved();
  }

  function renderTabsOnly() {
    const tab = list.children[active];
    if (!tab) return;
    const p = draft[active];
    tab.firstChild.textContent = p.name.trim() || hostOf(p.base_url) || '新服务商';
    tab.lastChild.textContent = hostOf(p.base_url) || '还没有填地址';
  }

  function extraProblem(p) {
    if (!p.extraText.trim()) return null;
    try {
      const value = JSON.parse(p.extraText);
      if (!value || typeof value !== 'object' || Array.isArray(value)) return '需要是一个 JSON 对象，比如 {"n": 1}。';
    } catch {
      return '不是合法的 JSON。';
    }
    return null;
  }

  async function save() {
    formError.textContent = '';
    const providers = [];
    for (const [index, p] of draft.entries()) {
      const label = p.name.trim() || hostOf(p.base_url) || '新服务商';
      const problem = !p.base_url.trim() ? '还没有填接口地址' : extraProblem(p) && `额外参数${extraProblem(p)}`;
      if (problem) {
        active = index;
        renderList();
        renderForm();
        formError.textContent = `「${label}」${problem}`;
        return;
      }
      providers.push({
        id: p.id, name: label, base_url: p.base_url.trim(), api_key: p.api_key.trim(), api_mode: p.api_mode,
        models: p.modelsText.split(/[\n,]/).map((s) => s.trim()).filter(Boolean),
        extra: p.extraText.trim() ? JSON.parse(p.extraText) : {},
        stream: p.api_mode !== 'chat' && Boolean(p.stream),
        timeout: Number(p.timeout) || state.defaults.timeout,
      });
    }
    saveButton.disabled = true;
    try {
      const config = await api('PUT', 'api/providers', { providers });
      state.providers = config.providers;
    } catch (error) {
      formError.textContent = error.message;
      return;
    } finally {
      saveButton.disabled = false;
    }
    fixPick();
    renderPickers();
    if (!state.messages.length) renderFeed();
    dialog.close();
    toast('接口设置已保存');
  }

  async function requestClose() {
    if (snapshot() !== initial) {
      const discard = await confirmDialog({ title: '放弃没保存的修改？', body: '刚才对接口设置的改动不会保留。', confirm: '放弃修改', danger: true });
      if (!discard) return;
    }
    dialog.close();
  }

  dialog.addEventListener('cancel', (event) => { event.preventDefault(); requestClose(); }); // Esc
  renderList();
  renderForm();
  showDialog(dialog);
  const first = $('input', form);
  if (first && !draft[active].base_url) first.focus();
}

/* ============================================================
 * 轮询与启动
 * ============================================================ */

async function refreshSessions() {
  try {
    state.sessions = await api('GET', 'api/sessions');
    renderSessions();
  } catch { /* 下一轮再试 */ }
}

let polling = false;

async function poll() {
  if (polling) return;
  const waiting = state.messages.filter((m) => m.status === 'pending').map((m) => m.id);
  if (!waiting.length && !state.sessions.some((s) => s.pending)) return;
  polling = true;
  try {
    if (waiting.length) {
      const fresh = await api('GET', `api/messages?ids=${waiting.join(',')}`);
      for (const message of fresh) {
        if (message.session_id !== state.currentId) continue;
        if (message.status !== 'pending') {
          replaceCard(message);
        } else if (message.previews.length) {
          const card = els.cards.querySelector(`[data-id="${message.id}"]`);
          if (card) showPreviews(card, message);
        }
      }
    }
    await refreshSessions();
  } catch { /* 后台暂时没响应，下一轮再试 */ } finally {
    polling = false;
  }
}

function tickClocks() {
  for (const el of document.querySelectorAll('.elapsed')) el.textContent = elapsed(Number(el.dataset.since));
}

function bindDevtools() {
  // 桌面窗口里按 Ctrl+Shift+I（macOS 是 ⌘⌥I）或 F12 打开内核的开发者工具；浏览器里交给浏览器自己
  document.addEventListener('keydown', (event) => {
    if (!state.native || event.repeat) return;
    const combo = (event.code === 'KeyI' && ((event.ctrlKey && event.shiftKey) || (event.metaKey && event.altKey))) ||
      event.key === 'F12';
    if (!combo) return;
    event.preventDefault();
    api('POST', 'api/devtools').catch((error) => toast(error.message, 'error'));
  }, true);
}

async function boot() {
  bindComposer();
  bindContextMenus();
  bindDevtools();
  let data;
  try {
    data = await api('GET', 'api/state');
  } catch (error) {
    els.cards.append(h('div', { class: 'empty' }, h('h2', null, '启动失败'), h('p', null, error.message)));
    return;
  }
  state.native = data.native;
  state.providers = data.config.providers;
  state.options = data.options;
  state.defaults = data.defaults;
  state.sessions = data.sessions;
  Object.assign(state.pick, data.config.last);
  fixPick();

  renderPickers();
  renderSessions();
  renderFeed();
  syncComposer();
  els.prompt.focus();
  setInterval(poll, 1500);
  setInterval(tickClocks, 1000);
}

window.addEventListener('load', syncTitle);
boot();
