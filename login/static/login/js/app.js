/* Inventory & Order Management — frontend */
(() => {
  'use strict';

  /* ── Utilities ───────────────────────────── */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const CAN_WRITE = document.body.dataset.canWrite === '1';

  const esc = (v) =>
    String(v ?? '').replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));

  const money = (v) => '\u20b9' + Number(v || 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const fmtDate = (v) =>
    v ? new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

  /* ── API client ──────────────────────────── */
  const csrf = document.querySelector('meta[name="csrf"]')?.content || '';

  async function api(path, { method = 'GET', body = null } = {}) {
    const opts = { method, headers: { 'X-CSRFToken': csrf } };
    if (body !== null) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch('/api' + path, opts);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = data && Object.entries(data).length
        ? Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('; ')
        : `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  /* ── Toast & modal helpers ───────────────── */
  function toast(msg, kind = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.textContent = msg;
    $('#toast-root').appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function closeModal() {
    $('#modal-root').innerHTML = '';
  }

  function openModal(html) {
    const root = $('#modal-root');
    root.innerHTML = `
      <div class="modal-overlay">
        <div class="modal">${html}</div>
      </div>`;
    $('.modal-overlay').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) closeModal();
    });
    $('.modal-close')?.addEventListener('click', closeModal);
    return $('.modal');
  }

  function buildForm(fields, values = {}) {
    return fields.map((f) => {
      const val = values[f.name] ?? '';
      let control;
      if (f.type === 'select') {
        const opts = (f.options || [])
          .map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(val) ? 'selected' : ''}>${esc(o.label)}</option>`)
          .join('');
        control = `<select class="input" name="${f.name}" ${f.required ? 'required' : ''}>${opts}</select>`;
      } else if (f.type === 'textarea') {
        control = `<textarea class="input" name="${f.name}" rows="3">${esc(val)}</textarea>`;
      } else {
        control = `<input class="input" name="${f.name}" type="${f.type || 'text'}" ${f.step ? `step="${f.step}"` : ''} ${f.required ? 'required' : ''} value="${esc(val)}">`;
      }
      return `<div class="form-row"><label>${esc(f.label)}</label>${control}</div>`;
    }).join('');
  }

  function formModal(title, fields, values, onSubmit) {
    const modal = openModal(`
      <div class="modal-head"><h3>${esc(title)}</h3><button class="modal-close" type="button">&times;</button></div>
      <form class="modal-body" id="modal-form">${buildForm(fields, values)}</form>
      <div class="modal-foot">
        <button class="btn btn-plain" type="button" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" type="submit" form="modal-form">Save</button>
      </div>`);
    $('#modal-cancel').addEventListener('click', closeModal);
    $('#modal-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = {};
      fields.forEach((f) => {
        const el = modal.querySelector(`[name="${f.name}"]`);
        if (!el) return;
        data[f.name] = (f.type === 'number') ? parseFloat(el.value) : el.value.trim();
      });
      await onSubmit(data);
    });
  }

  function badge(text, cls) {
    return `<span class="badge ${cls}">${esc(text)}</span>`;
  }

  const statusBadge = (s) => badge(s, s);

  const stockBadge = (q, reorder) =>
    q <= 0 ? badge('Out of stock', 'out') : q <= reorder ? badge('Low stock', 'low') : badge('In stock', 'in-stock');

  async function loadVendors() {
    const data = await api('/vendors/');
    return data.map((v) => ({ value: v.id, label: v.name }));
  }

  /* ── Dashboard ───────────────────────────── */
  async function dashboard() {
    try {
      const [summary, top, vendors] = await Promise.all([
        api('/reports/summary/'),
        api('/reports/top-products/'),
        api('/reports/vendors/'),
      ]);

      const p = summary.products;
      const o = summary.orders;
      const cards = [
        { label: 'Products', value: p.total, cls: '' },
        { label: 'Stock units', value: p.total_stock_units, cls: 'success' },
        { label: 'Stock value', value: money(p.stock_value), cls: '' },
        { label: 'Low stock', value: p.low_stock, cls: 'warn', sub: `${p.out_of_stock} out of stock` },
        { label: 'Orders', value: o.total, cls: '' },
        { label: 'Revenue', value: money(o.revenue), cls: 'success' },
      ];
      $('#stat-cards').innerHTML = cards.map((c) => `
        <div class="stat ${c.cls}">
          <div class="label">${c.label}</div>
          <div class="value">${c.value}</div>
          ${c.sub ? `<div class="sub">${c.sub}</div>` : ''}
        </div>`).join('');

      const statuses = [['pending', 'Pending'], ['processed', 'Processed'], ['shipped', 'Shipped'], ['cancelled', 'Cancelled']];
      const max = Math.max(...statuses.map(([k]) => o.by_status[k] || 1), 1);
      $('#status-bars').innerHTML = statuses.map(([k, label]) => `
        <div class="bar-row">
          <span>${label}</span>
          <div class="track"><div class="fill" style="width:${(o.by_status[k] / max) * 100}%"></div></div>
          <span class="val">${o.by_status[k]}</span>
        </div>`).join('');

      $('#top-products').innerHTML = top.products.length
        ? top.products.map((t) => `
            <tr>
              <td>${esc(t.product__name)} <small class="muted">${esc(t.product__sku)}</small></td>
              <td class="num">${t.units_sold}</td>
              <td class="num">${money(t.revenue)}</td>
            </tr>`).join('')
        : '<tr><td colspan="3" class="empty">No sales yet.</td></tr>';

      $('#vendor-report').innerHTML = vendors.vendors.length
        ? vendors.vendors.map((v) => `
            <tr>
              <td>${esc(v.name)}</td>
              <td class="num">${v.products}</td>
              <td class="num">${v.orders}</td>
              <td class="num">${money(v.revenue)}</td>
            </tr>`).join('')
        : '<tr><td colspan="4" class="empty">No vendors yet.</td></tr>';
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  /* ── Products ────────────────────────────── */
  async function products() {
    let search = '';
    let lowStock = false;

    async function render() {
      let q = '';
      if (search) q += `${q ? '&' : '?'}search=${encodeURIComponent(search)}`;
      if (lowStock) q += `${q ? '&' : '?'}low_stock=true`;
      const data = await api('/products/' + q);
      $('#empty').classList.toggle('hidden', data.length > 0);
      $('#rows').innerHTML = data.length
        ? data.map((p) => `
            <tr>
              <td>${esc(p.sku)}</td>
              <td>${esc(p.name)}</td>
              <td>${esc(p.vendor?.name || '—')}</td>
              <td class="num">${money(p.price)}</td>
              <td class="num">${p.stock_quantity}</td>
              <td class="num">${p.reorder_level}</td>
              <td>${stockBadge(p.stock_quantity, p.reorder_level)}</td>
              ${CAN_WRITE ? `
              <td class="actions">
                <button class="btn btn-plain btn-sm" data-edit="${p.id}">Edit</button>
                <button class="btn btn-danger btn-sm" data-del="${p.id}">Delete</button>
              </td>` : ''}
            </tr>`).join('')
        : '';
    }

    async function productForm(id = null) {
      const vendors = await loadVendors();
      const fields = window.PRODUCT_FORM.map((f) =>
        f.name === 'vendor_id' ? { ...f, options: vendors } : f,
      );
      let values = {};
      if (id) {
        const p = await api(`/products/${id}/`);
        values = { ...p, vendor_id: p.vendor?.id ?? '' };
      }
      formModal(id ? 'Edit Product' : 'New Product', fields, values, async (data) => {
        try {
          if (id) { await api(`/products/${id}/`, { method: 'PUT', body: data }); toast('Product updated'); }
          else { await api('/products/', { method: 'POST', body: data }); toast('Product created'); }
          closeModal();
          await render();
        } catch (err) { toast(err.message, 'error'); }
      });
    }

    $('#search').addEventListener('input', (e) => { search = e.target.value; render(); });
    $('#low-stock').addEventListener('change', (e) => { lowStock = e.target.checked; render(); });
    $('#add-btn').addEventListener('click', () => productForm());
    $('#rows').addEventListener('click', async (e) => {
      const edit = e.target.closest('[data-edit]');
      const del = e.target.closest('[data-del]');
      if (edit) return productForm(edit.dataset.edit);
      if (del && confirm('Delete this product?')) {
        try {
          await api(`/products/${del.dataset.del}/`, { method: 'DELETE' });
          toast('Product deleted');
          await render();
        } catch (err) { toast(err.message, 'error'); }
      }
    });

    render();
  }

  /* ── Vendors ─────────────────────────────── */
  async function vendors() {
    let search = '';

    async function render() {
      const q = search ? `?search=${encodeURIComponent(search)}` : '';
      const data = await api('/vendors/' + q);
      $('#empty').classList.toggle('hidden', data.length > 0);
      $('#rows').innerHTML = data.length
        ? data.map((v) => `
            <tr>
              <td>${esc(v.name)}</td>
              <td>${esc(v.contact_person)}</td>
              <td>${esc(v.email)}</td>
              <td>${esc(v.phone || '—')}</td>
              <td>${fmtDate(v.created_at)}</td>
              ${CAN_WRITE ? `
              <td class="actions">
                <button class="btn btn-plain btn-sm" data-edit="${v.id}">Edit</button>
                <button class="btn btn-danger btn-sm" data-del="${v.id}">Delete</button>
              </td>` : ''}
            </tr>`).join('')
        : '';
    }

    async function vendorForm(id = null) {
      let values = {};
      if (id) {
        const v = await api(`/vendors/${id}/`);
        values = v;
      }
      formModal(id ? 'Edit Vendor' : 'New Vendor', window.VENDOR_FORM, values, async (data) => {
        try {
          if (id) { await api(`/vendors/${id}/`, { method: 'PUT', body: data }); toast('Vendor updated'); }
          else { await api('/vendors/', { method: 'POST', body: data }); toast('Vendor created'); }
          closeModal();
          await render();
        } catch (err) { toast(err.message, 'error'); }
      });
    }

    $('#search').addEventListener('input', (e) => { search = e.target.value; render(); });
    $('#add-btn').addEventListener('click', () => vendorForm());
    $('#rows').addEventListener('click', async (e) => {
      const edit = e.target.closest('[data-edit]');
      const del = e.target.closest('[data-del]');
      if (edit) return vendorForm(edit.dataset.edit);
      if (del && confirm('Delete this vendor?')) {
        try {
          await api(`/vendors/${del.dataset.del}/`, { method: 'DELETE' });
          toast('Vendor deleted');
          await render();
        } catch (err) { toast(err.message, 'error'); }
      }
    });

    render();
  }

  /* ── Orders ──────────────────────────────── */
  async function orders() {
    async function render() {
      const data = await api('/orders/');
      $('#empty').classList.toggle('hidden', data.length > 0);
      $('#rows').innerHTML = data.length
        ? data.map((o) => `
            <tr>
              <td>${esc(o.order_number)}</td>
              <td>${esc(o.customer_name)}<br><small class="muted">${esc(o.customer_email)}</small></td>
              <td>${esc(o.vendor?.name || '—')}</td>
              <td class="num">${money(o.total_amount)}</td>
              <td>${statusBadge(o.status)}</td>
              <td>${fmtDate(o.created_at)}</td>
              ${CAN_WRITE ? `
              <td class="actions">
                ${o.status === 'pending' ? `<button class="btn btn-success btn-sm" data-act="process" data-id="${o.id}">Process</button>` : ''}
                ${o.status === 'processed' ? `<button class="btn btn-success btn-sm" data-act="ship" data-id="${o.id}">Ship</button>` : ''}
                ${(o.status === 'pending' || o.status === 'processed') ? `<button class="btn btn-danger btn-sm" data-act="cancel" data-id="${o.id}">Cancel</button>` : ''}
              </td>` : ''}
            </tr>`).join('')
        : '';
    }

    async function orderForm() {
      const [vendors, products] = await Promise.all([loadVendors(), api('/products/')]);
      const modal = openModal(`
        <div class="modal-head"><h3>New Order</h3><button class="modal-close" type="button">&times;</button></div>
        <form class="modal-body" id="order-form">
          <div class="form-grid-2">
            <div class="form-row"><label>Customer name</label><input class="input" name="customer_name" required></div>
            <div class="form-row"><label>Customer email</label><input class="input" name="customer_email" type="email" required></div>
          </div>
          <div class="form-row">
            <label>Vendor</label>
            <select class="input" name="vendor_id">${vendors.map((v) => `<option value="${v.value}">${esc(v.label)}</option>`).join('')}</select>
          </div>
          <div class="form-row">
            <label>Items</label>
            <div id="items"></div>
            <button type="button" class="btn btn-plain btn-sm" id="add-item">+ Add item</button>
          </div>
        </form>
        <div class="modal-foot">
          <button class="btn btn-plain" type="button" id="modal-cancel">Cancel</button>
          <button class="btn btn-primary" type="submit" form="order-form">Create Order</button>
        </div>`);

      $('#modal-cancel').addEventListener('click', closeModal);

      const productOptions = () => products.map((p) =>
        `<option value="${p.id}" data-price="${p.price}" data-stock="${p.stock_quantity}">${esc(p.name)} (${esc(p.sku)})</option>`).join('');

      function addItemRow() {
        const row = document.createElement('div');
        row.className = 'item-row';
        row.innerHTML = `
          <select class="input" name="product">${productOptions()}</select>
          <input class="input" name="quantity" type="number" min="1" value="1" required>
          <input class="input" name="unit_price" type="number" min="0" step="0.01" required>
          <button type="button" class="btn btn-danger btn-sm" title="Remove">×</button>`;
        const sync = () => {
          const sel = row.querySelector('[name="product"]');
          row.querySelector('[name="unit_price"]').value = sel.selectedOptions[0]?.dataset.price ?? '';
        };
        row.querySelector('[name="product"]').addEventListener('change', sync);
        row.querySelector('button').addEventListener('click', () => { row.remove(); });
        $('#items').appendChild(row);
        sync();
      }

      $('#add-item').addEventListener('click', addItemRow);
      addItemRow();

      $('#order-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const items = $$('#items .item-row').map((row) => ({
          product_id: parseInt(row.querySelector('[name="product"]').value, 10),
          quantity: parseInt(row.querySelector('[name="quantity"]').value, 10),
          unit_price: parseFloat(row.querySelector('[name="unit_price"]').value),
        }));
        if (!items.length) return toast('Add at least one item.', 'error');
        const payload = {
          customer_name: $('#order-form [name="customer_name"]').value.trim(),
          customer_email: $('#order-form [name="customer_email"]').value.trim(),
          vendor_id: parseInt($('#order-form [name="vendor_id"]').value, 10),
          items,
        };
        try {
          const order = await api('/orders/', { method: 'POST', body: payload });
          toast(`Order ${order.order_number} created — stock deducted`);
          closeModal();
          await render();
        } catch (err) { toast(err.message, 'error'); }
      });
    }

    $('#add-btn').addEventListener('click', orderForm);
    $('#rows').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-act]');
      if (!btn) return;
      try {
        await api(`/orders/${btn.dataset.id}/${btn.dataset.act}/`, { method: 'POST' });
        toast(`Order ${btn.dataset.act} successful`);
        await render();
      } catch (err) { toast(err.message, 'error'); }
    });

    render();
  }

  /* ── Invoices ────────────────────────────── */
  async function invoices() {
    const data = await api('/invoices/');
    $('#empty').classList.toggle('hidden', data.length > 0);
    $('#rows').innerHTML = data.length
      ? data.map((inv) => `
          <tr>
            <td>${esc(inv.invoice_number)}</td>
            <td>${esc(inv.order?.order_number || '—')}</td>
            <td>${esc(inv.customer_name)}</td>
            <td class="num">${money(inv.total_amount)}</td>
            <td>${fmtDate(inv.issued_at)}</td>
            <td><a class="btn btn-primary btn-sm" href="/api/invoices/${inv.id}/download/">Download PDF</a></td>
          </tr>`).join('')
      : '';
  }

  /* ── Alerts ──────────────────────────────── */
  async function alerts() {
    let showResolved = false;

    async function render() {
      const q = showResolved ? '?resolved=true' : '?resolved=false';
      const data = await api('/alerts/' + q);
      $('#empty').classList.toggle('hidden', data.length > 0);
      $('#rows').innerHTML = data.length
        ? data.map((a) => `
            <tr>
              <td>${esc(a.product_name || '—')}</td>
              <td>${esc(a.message)}</td>
              <td>${fmtDate(a.created_at)}</td>
              <td>${a.resolved ? badge('Resolved', 'in-stock') : badge('Open', 'out')}</td>
              ${CAN_WRITE ? `<td>${a.resolved ? '' : `<button class="btn btn-success btn-sm" data-resolve="${a.id}">Mark resolved</button>`}</td>` : ''}
            </tr>`).join('')
        : '';
    }

    $('#show-resolved').addEventListener('change', (e) => { showResolved = e.target.checked; render(); });
    $('#rows').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-resolve]');
      if (!btn) return;
      try {
        await api(`/alerts/${btn.dataset.resolve}/resolve/`, { method: 'POST' });
        toast('Alert resolved');
        await render();
      } catch (err) { toast(err.message, 'error'); }
    });

    render();
  }

  /* ── Movements ───────────────────────────── */
  async function movements() {
    let type = '';

    async function render() {
      const q = type ? `?type=${type}` : '';
      const data = await api('/stock-movements/' + q);
      $('#empty').classList.toggle('hidden', data.length > 0);
      $('#rows').innerHTML = data.length
        ? data.map((m) => `
            <tr>
              <td>${esc(m.product_name || '—')}</td>
              <td>${badge(m.movement_type, m.movement_type)}</td>
              <td>${esc(m.reference_type)} ${esc(m.reference_id || '')}</td>
              <td class="num">${m.quantity}</td>
              <td class="num">${m.previous_quantity}</td>
              <td class="num">${m.new_quantity}</td>
              <td>${esc(m.notes || '—')}</td>
              <td>${fmtDate(m.created_at)}</td>
            </tr>`).join('')
        : '';
    }

    $('#type').addEventListener('change', (e) => { type = e.target.value; render(); });
    render();
  }

  /* ── Boot ────────────────────────────────── */
  const page = document.body.dataset.page;

  $$('.nav-link[data-nav]').forEach((link) => {
    if (link.dataset.nav === page) link.classList.add('active');
  });

  const init = { dashboard, products, vendors, orders, invoices, alerts, movements };
  (init[page] || (() => {}))();

})();
