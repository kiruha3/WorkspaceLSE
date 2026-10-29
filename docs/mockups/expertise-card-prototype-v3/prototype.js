/* Standalone UI spike. All changes are in memory. No application/API dependencies. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const today = '2026-10-29';
  const date = value => value ? String(value).split('-').reverse().join('.') : 'Не указана';
  const kinds = {basis:'Постановление / определение',expert_conclusion:'Заключение эксперта',sndz:'СНДЗ',research_act:'Акт экспертного исследования',subscription:'Подписка эксперта',cover:'Сопроводительное письмо',notification:'Уведомление',invoice:'Счёт',other:'Другой документ'};
  const resultKinds = ['expert_conclusion','sndz','research_act'];
  const statuses = {in_progress:'В производстве',suspended:'Приостановлена',completed:'Завершена',without_execution:'Без исполнения'};
  const tabs = {work:'Работа',case:'Дело',documents:'Документы',letters:'Переписка',issuance:'Выдача',history:'История'};
  const scenarios = {working:'В производстве',saved:'Результат сохранён',suspended:'Приостановлена',completed:'Завершена, не выдана',issued:'Материалы выданы',sndz:'Полное СНДЗ',research:'Экспертное исследование',commission:'Комиссионная',complex:'Комплексная',returned:'Без исполнения'};
  const rights = {
    full:['case','assign','result','closed_correct','pause','resume','complete','return','reopen','documents','letters','issue_prepare','issue_check','issue_confirm'],
    expert:['case','result','pause','resume','complete','return','documents','letters'],
    clerk:['case','pause','resume','documents','letters','issue_prepare','issue_check','issue_confirm'],
    reader:[]
  };
  const rightNames = {case:'Редактировать сведения экспертизы',assign:'Назначать экспертов',result:'Редактировать результат',closed_correct:'Корректировать завершённые экспертизы',pause:'Приостанавливать работу',resume:'Возобновлять работу',complete:'Завершать экспертизы',return:'Возвращать без исполнения',reopen:'Возвращать завершённую экспертизу в работу',documents:'Добавлять документы',letters:'Работать с перепиской',issue_prepare:'Готовить выдачу',issue_check:'Проверять комплект',issue_confirm:'Подтверждать выдачу'};
  const urls = new Set();
  let state, ui, modal, counter = 0, toastTimer, tipTimer, tipAnchor, tipPinned = false, uploading = false, expansion;
  const uid = prefix => `${prefix}-${++counter}`;
  const help = (text, label = 'Пояснение') => `<button type="button" class="lse-help" data-help="${h(text)}" aria-label="${h(label)}">?</button>`;
  const button = (action, label, options = {}) => {
    const reason = options.reason || denied(action);
    return `<span class="lse-action-group"><button type="button" data-action="${h(action)}"${options.id ? ` data-id="${h(options.id)}"` : ''} class="${options.primary ? 'lse-primary' : ''} ${options.text ? 'lse-text-action' : ''}"${reason ? ` aria-disabled="true" data-denied="${h(reason)}"` : ''}>${h(label)}</button>${reason ? help(reason, `Почему недоступно: ${label}`) : options.tip ? help(options.tip) : ''}</span>`;
  };
  function permissionFor(action) {
    return {editcase:'case',classification:'case',assign:'assign',editresult:state?.status === 'completed' ? 'closed_correct' : 'result',save_result:state?.status === 'completed' ? 'closed_correct' : 'result',pause:'pause',resume:'resume',complete:'complete',return:'return',reopen:'reopen',upload:'documents',scan:'documents',version:'documents',upload_result:'documents',letter:'letters',deadline:'case',prepare:'issue_prepare',check:'issue_check',issue:'issue_confirm'}[action];
  }
  function denied(action) {
    if (!state) return '';
    const permission = permissionFor(action);
    if (permission && !rights[ui.profile].includes(permission)) return `В этом профиле нет права «${rightNames[permission]}». В рабочей АИС его назначают через роль сотрудника.`;
    const closed = ['completed','without_execution'].includes(state.status);
    if (['editcase','classification','assign','deadline','pause','resume','return'].includes(action) && closed) return 'Работа завершена. Для изменения рабочего процесса сначала верните её в работу.';
    if (action === 'pause' && state.status !== 'in_progress') return 'Приостановить можно работу в производстве.';
    if (action === 'resume' && state.status !== 'suspended') return 'Сейчас нет действующей приостановки.';
    if (action === 'complete') {
      if (state.status !== 'in_progress') return state.status === 'suspended' ? 'Сначала возобновите работу.' : 'Работа уже завершена.';
      if (!state.result) return 'Сначала сохраните результат экспертизы.';
      if (!state.result.completed_on) return 'В результате не указана дата окончания. Нажмите «Редактировать».';
      if (ui.editing) return 'Сначала сохраните или отмените изменения результата.';
    }
    if (['editresult','save_result'].includes(action) && state.status === 'without_execution') return 'Работа возвращена без исполнения. Результат для неё не оформляется.';
    if (action === 'reopen') {
      if (state.issued) return 'Материалы уже выданы. Возврат в работу недоступен после выдачи; это ограничение состояния, а не роли.';
      if (state.status !== 'completed') return 'Это действие предназначено для завершённой экспертизы.';
    }
    if (['prepare','check','issue'].includes(action) && state.issued) return 'Выдача уже зарегистрирована.';
    if (action === 'check' && !state.materials.trim()) return 'Сначала укажите состав возвращаемых материалов.';
    if (action === 'issue') {
      if (!closed) return 'Сначала завершите работу.';
      if (state.complex && !state.relatedClosed) return 'Другая работа по этим материалам ещё в производстве. Материалы выдаются после завершения всех связанных работ.';
      if (!state.materials.trim()) return 'Не указан состав возвращаемых материалов.';
      if (!state.checked) return 'Нажмите «Проверить комплект». Проверка нужна после последнего изменения документов или состава материалов.';
    }
    return '';
  }
  const field = (name, label, value = '', type = 'text', extra = '') => `<label class="lse-field"><span>${h(label)}</span><input name="${name}" type="${type}" value="${h(value)}" ${extra}></label>`;
  const area = (name, label, value = '', extra = '') => `<label class="lse-field lse-wide"><span>${h(label)}</span><textarea name="${name}" rows="2" ${extra}>${h(value)}</textarea></label>`;
  const select = (name, label, values, value, extra = '') => `<label class="lse-field"><span>${h(label)}</span><select name="${name}" ${extra}>${Object.entries(values).map(([k,v]) => `<option value="${h(k)}"${String(value) === k ? ' selected' : ''}>${h(v)}</option>`).join('')}</select></label>`;
  const reasonField = () => area('reason','Основание изменения','', 'required');
  const emptyResult = kind => ({kind:kind || 'expert_conclusion',completed_on:'',documentId:null,note:'',complexity:'',q:'',r:'',s:'',t:'',statistics_complete:false,allocations_complete:false,sndz_reason:'science',sndz_comment:'',reason:''});
  function demoDoc(kind, title, withFile = false) {
    return {id:uid('doc'),kind,title,source:withFile ? 'copy' : 'paper',versions:withFile ? [{id:uid('v'),name:`${title}.pdf`,type:'application/pdf',demo:true}] : []};
  }
  function reset(scenario = 'working') {
    if (uploading) return;
    for (const url of urls) URL.revokeObjectURL(url);
    urls.clear();
    const profile = ui?.profile || 'full';
    const basis = demoDoc('basis','Постановление о назначении экспертизы',false);
    state = {scenario,number:'482/4-1-26',specialty:'19.1',department:'4',category:'1',status:'in_progress',received:today,employees:['Лалетина О.В.'],deadline:'',commission:false,complex:false,relatedClosed:false,classification:'primary',result:null,issued:null,materials:'',paid:false,checked:false,docs:[basis],basisId:basis.id,letters:[],history:[{title:'Зарегистрирована экспертиза',detail:'29.10.2026 · условный пример для проверки интерфейса'}],case:{authority:'ОтдМВД России по г. Абаза',official:'ст. следователь СО Филинова Ю.А.',contact:'',case_number:'12601950001001915',description:'Стоимость велосипеда BMX',basis_text:'Постановление о назначении судебной экспертизы',inventory:'Велосипед и материалы дела',questions_text:''}};
    if (scenario === 'research') {state.category = '6'; state.number = '482/4-6-26';}
    if (['saved','completed','issued','sndz','research'].includes(scenario)) {
      const kind = scenario === 'sndz' ? 'sndz' : scenario === 'research' ? 'research_act' : 'expert_conclusion';
      const doc = demoDoc(kind,`${kinds[kind]} № ${state.number}`,true);
      state.docs.push(doc);
      state.result = {...emptyResult(kind),completed_on:today,documentId:doc.id,reason:'Пример сохранённого результата'};
    }
    if (scenario === 'suspended') {state.status = 'suspended';state.pause = {date:today,reason:'Ожидание дополнительных материалов'};}
    if (['completed','issued'].includes(scenario)) {state.status = 'completed';state.history.push({title:'Экспертиза завершена',detail:'29.10.2026 · выдача оформляется отдельно'});}
    if (scenario === 'issued') {state.issued = {date:today,recipient:'Представитель назначившего органа (пример)',method:'Лично'};state.materials = state.case.inventory;state.checked = true;}
    if (scenario === 'commission') {state.commission = true;state.employees.push('Второй эксперт (пример)');}
    if (scenario === 'complex') {state.complex = true;}
    if (scenario === 'returned') {state.status = 'without_execution';state.history.push({title:'Возвращена без исполнения',detail:'Условный пример возврата'});}
    if (expansion) expansion.seed(scenario);
    ui = {profile,tab:'work',editing:false,draft:null,notice:''};
    $('#lab-scenario').value = scenario;
    closeDialog(); render();
  }
  function event(title, detail = '') {state.history.push({title,detail:`${date(today)} · ${detail || 'Изменение в прототипе'}`});}
  function notice(text) {ui.notice = text;render();}
  function toast(text) {clearTimeout(toastTimer);$('#lse-toast').textContent = text;$('#lse-toast').hidden = false;toastTimer = setTimeout(() => {$('#lse-toast').hidden = true;},3500);}
  function currentDoc(id) {return state.docs.find(d => d.id === id);}
  function sourceLabel(doc) {return doc.versions.length ? `${doc.versions.length} ${doc.versions.length === 1 ? 'версия' : 'версии'} · ${doc.versions.at(-1).name}` : doc.source === 'link' ? 'Ссылка на документ' : 'Бумажный оригинал · скан не добавлен';}
  function docRow(doc, picker = false) {
    const active = ui.draft?.documentId === doc.id || state.result?.documentId === doc.id;
    return `<div class="lse-doc-row${active && !picker ? ' lse-doc-selected' : ''}"><span class="lse-doc-icon" aria-hidden="true">▤</span><div><div class="lse-doc-title">${h(doc.title)}</div><div class="lse-doc-meta">${h(kinds[doc.kind] || doc.kind)} · ${h(sourceLabel(doc))}</div></div><div class="lse-doc-actions">${picker ? button('choose_doc','Выбрать',{id:doc.id}) : button('view','Открыть',{id:doc.id,text:true})}${!picker && doc.kind === 'basis' ? button('scan',doc.versions.length ? 'Новая версия' : 'Добавить скан',{id:doc.id,text:true}) : ''}</div></div>`;
  }
  function identity() {
    const statusClass = state.status === 'suspended' ? 'lse-paused' : state.status === 'without_execution' ? 'lse-returned' : state.status === 'completed' ? 'lse-closed' : '';
    return `<div class="lse-heading"><div><div class="lse-heading-title"><h1>${h(state.number)}</h1><span class="lse-status ${statusClass}">${statuses[state.status]}</span>${state.issued ? '<span class="lse-status">Материалы выданы</span>' : ''}${state.commission ? '<span class="lse-tag">Комиссионная · один номер</span>' : ''}${state.complex ? '<span class="lse-tag">Комплексная · отдельные номера</span>' : ''}</div><p class="lse-meta"><span>Специальность ${h(state.specialty)}</span><span>Отдел ${h(state.department)}</span><span>Поступила ${date(state.received)}</span></p></div><div class="lse-heading-actions">${button('editcase','Редактировать дело')}${help('Номер, отдел, поступление и состояние видны постоянно. Документы, переписка, выдача и история доступны во вкладках. Это отдельный макет, а не рабочая карточка.')}</div></div>`;
  }
  function dataRow(label, value, actions = '', hint = '') {return `<div class="lse-data-row"><div class="lse-row-label">${h(label)}${hint ? help(hint) : ''}</div><div class="lse-row-value">${value}</div><div class="lse-row-action">${actions}</div></div>`;}
  function resultLabel() {return state.result ? kinds[state.result.kind] : 'Не добавлен';}
  function reportGaps() {
    const gaps = [];
    if (!state.deadline) gaps.push('Срок не указан');
    if (!state.result) gaps.push('Результат не сохранён');
    else {if (!state.result.statistics_complete) gaps.push('Статистика вопросов не заполнена');if (!state.result.complexity) gaps.push('Сложность не указана');}
    if (!currentDoc(state.basisId)?.versions.length) gaps.push('Нет скана постановления');
    if (!currentDoc(state.result?.documentId)) gaps.push('Не прикреплён итоговый документ');
    return gaps;
  }
  function work() {
    const main = ui.editing ? resultEditor() : `<section class="lse-surface"><div class="lse-section-head"><h2>Работа по экспертизе</h2>${help('Назначение, срок и результат редактируются отдельно. Сохранение результата не завершает экспертизу; завершение не означает выдачу материалов.')}</div>${dataRow('Исполнитель',state.employees.map(h).join('<br>'),button('assign','Редактировать'),state.commission ? 'На комиссионной работе несколько экспертов под одним номером. Подписка оформляется на каждого.' : 'Назначает начальник отдела или сотрудник с соответствующим правом.')}${dataRow('Срок',state.deadline ? date(state.deadline) : '<span class="lse-muted">Не указан</span>',button('deadline','Редактировать'))}${state.pause ? dataRow('Приостановка',`${date(state.pause.date)}<small>${h(state.pause.reason)}</small>`,button('resume','Возобновить')) : ''}${dataRow('Результат',`${h(resultLabel())}${state.result ? `<small>${date(state.result.completed_on)} · ${state.status === 'in_progress' ? 'сохранён, работа продолжается' : 'сохранён'}</small>` : ''}`,button('editresult',state.result ? 'Редактировать' : 'Добавить'))}<div class="lse-work-actions">${state.status === 'completed' ? button('reopen','Вернуть в работу') : state.status === 'suspended' ? button('resume','Возобновить') : button('pause','Приостановить')}${!['completed','without_execution'].includes(state.status) ? button('return','Без исполнения') : ''}<span class="lse-next">${state.status === 'completed' || state.status === 'without_execution' ? button('to_issuance',state.issued ? 'Посмотреть выдачу' : 'Перейти к выдаче',{primary:true}) : !state.result ? button('editresult','Добавить результат',{primary:true}) : button('complete','Завершить экспертизу',{primary:true})}</span></div></section>`;
    const resultDoc = currentDoc(ui.editing ? ui.draft.documentId : state.result?.documentId);
    const docPanel = `<section class="lse-surface"><div class="lse-section-head"><h2>Документы</h2>${button('upload','Добавить файл в дело',{text:true})}</div>${docRow(currentDoc(state.basisId))}${resultDoc ? docRow(resultDoc) : `<div class="lse-doc-row"><span class="lse-doc-icon" aria-hidden="true">▤</span><div><div class="lse-doc-title">${h(kinds[ui.draft?.kind || state.result?.kind || (state.category === '6' ? 'research_act' : 'expert_conclusion')])}</div><div class="lse-doc-meta">Документ не прикреплён</div></div><div class="lse-doc-actions">${button('upload_result','Загрузить',{text:true})}</div></div>`}${state.docs.filter(d => d.kind !== 'basis' && d.id !== resultDoc?.id).slice(0,2).map(d => docRow(d)).join('')}<div class="lse-helper-line">${button('to_documents',`Все документы (${state.docs.length})`,{text:true})}${help('«Добавить скан» добавляет файл к существующему постановлению. «Добавить файл в дело» создаёт отдельный документ. В рабочей версии файлы хранятся в настроенных папках; здесь они остаются только в памяти вкладки.')}</div></section>`;
    const gaps = reportGaps();
    return `${ui.profile === 'reader' ? `<p class="lse-readonly">Только просмотр ${help('Действия остаются на своих местах. Серые кнопки недоступны, а вопрос рядом объясняет необходимое право.')}</p>` : ''}<div class="lse-work-grid"><div>${main}${state.complex ? `<section class="lse-surface lse-related-panel"><div class="lse-section-head"><h2>Связанные работы</h2>${help('Комплексная экспертиза объединяет работы по общим материалам. На каждую специальность — свой номер. В макете показана ещё одна условная работа.')}</div><div class="lse-related">${button('related','483/4-1-26 · 18.1 · в производстве')}</div></section>` : ''}<details class="lse-disclosure"><summary>Для отчёта <span class="lse-summary-meta lse-attention">${gaps.length ? `Не заполнено: ${gaps.length}` : 'Сведения заполнены'}</span></summary><div class="lse-disclosure-body"><ul class="lse-checklist">${gaps.map(g => `<li><span class="lse-missingmark">•</span>${h(g)}</li>`).join('')}</ul><div class="lse-helper-line">${help('Этот список напоминает о неполных сведениях. Отсутствие сканов и отчётных показателей не блокирует завершение. Реальные ошибки данных показываются рядом с полем.')}${button('editresult','Редактировать результат',{text:true})}</div></div></details><details class="lse-disclosure"><summary>Регистрационные сведения <span class="lse-summary-meta">Дело и основание</span></summary><div class="lse-disclosure-body">${caseFacts()}</div></details></div>${docPanel}</div>`;
  }
  function caseFacts() {return `<dl class="lse-facts">${[['Категория дела',{'1':'Уголовное','2':'Гражданское','3':'Арбитражное','4':'КоАП','5':'КУСП','6':'По заявлению'}[state.category]],['Орган',state.case.authority],['Должностное лицо',state.case.official],['Номер дела',state.case.case_number],['Описание',state.case.description],['Основание',state.case.basis_text],['Материалы',state.case.inventory],['Вопросы',state.case.questions_text || 'Не указаны']].map(([k,v]) => `<div><dt>${h(k)}</dt><dd class="lse-preserve">${h(v)}</dd></div>`).join('')}</dl>`;}
  function casePage() {return `<div class="lse-stack"><section class="lse-surface"><div class="lse-section-head"><h2>Сведения о деле</h2>${button('editcase','Редактировать')}</div>${caseFacts()}</section><section class="lse-surface"><div class="lse-section-head"><h2>Характер экспертизы</h2>${button('classification','Редактировать')}</div><div class="lse-meta"><span>${{primary:'Первичная',additional:'Дополнительная',repeated:'Повторная'}[state.classification]}</span><span>${state.commission ? 'Комиссионная' : 'Единоличная'}</span>${state.complex ? '<span>Комплексная</span>' : ''}</div></section></div>`;}
  function documentsPage() {return `<section class="lse-surface"><div class="lse-section-head"><h2>Документы дела <span class="lse-muted">${state.docs.length}</span></h2>${button('upload','Добавить файл в дело',{primary:true})}</div><div class="lse-search-row"><input id="doc-search" type="search" placeholder="Найти по названию или имени файла" aria-label="Поиск документов дела"></div><div id="doc-list">${state.docs.map(d => docRow(d)).join('')}</div></section>`;}
  function lettersPage() {return `<section class="lse-surface"><div class="lse-section-head"><h2>Переписка по экспертизе</h2>${button('letter','Добавить письмо',{primary:true})}</div>${state.letters.length ? `<div class="lse-table-wrap"><table class="lse-table"><thead><tr><th>Дата</th><th>Направление</th><th>Тема</th><th></th></tr></thead><tbody>${state.letters.map(l => `<tr><td>${date(l.date)}</td><td>${h(l.direction)}</td><td>${h(l.subject)}<small>${h(l.recipient)}</small></td><td>${button('view_letter','Открыть',{id:l.id,text:true})}</td></tr>`).join('')}</tbody></table></div>` : '<p class="lse-empty">Писем по этой работе пока нет.</p>'}</section>`;}
  function requiredDocs() {
    let list = state.status === 'without_execution' ? ['cover'] : state.result?.kind === 'sndz' ? ['subscription','cover','sndz'] : ['subscription','cover',state.result?.kind || 'expert_conclusion'];
    if (state.status !== 'without_execution' && state.result?.kind !== 'sndz' && ['1','5'].includes(state.category)) list.push('notification');
    if (state.paid || ['2','3'].includes(state.category)) list.push('invoice');
    return list;
  }
  function issuancePage() {
    if (state.issued) return `<section class="lse-surface"><div class="lse-section-head"><h2>Материалы выданы</h2><span class="lse-status">${date(state.issued.date)}</span></div><dl class="lse-facts"><div><dt>Получатель</dt><dd>${h(state.issued.recipient)}</dd></div><div><dt>Способ выдачи</dt><dd>${h(state.issued.method)}</dd></div><div><dt>Материалы</dt><dd>${h(state.materials)}</dd></div><div><dt>Состояние работы</dt><dd>${statuses[state.status]}</dd></div></dl><div class="lse-work-actions">${button('reopen','Вернуть в работу')}</div></section>`;
    return `<div class="lse-work-grid"><section class="lse-surface"><div class="lse-section-head"><h2>Подготовка выдачи</h2>${help('Завершение работы и выдача материалов — разные события. Неполный комплект файлов показывается как предупреждение. Для выдачи нужен описанный состав материалов, завершённая работа и актуальная проверка комплекта.')}</div><div class="lse-form"><label class="lse-field"><span>Возвращаемые материалы</span><textarea id="issue-materials" rows="3"${!rights[ui.profile].includes('issue_prepare') ? ' disabled' : ''}>${h(state.materials)}</textarea></label><label class="lse-check"><input id="issue-paid" type="checkbox"${state.paid ? ' checked' : ''}${!rights[ui.profile].includes('issue_prepare') ? ' disabled' : ''}>Платная работа ${help('Для платной работы в комплекте нужен счёт. Отсутствие файла отмечается в предупреждениях.')}</label><div class="lse-form-footer">${button('prepare','Сохранить состав')}${button('check','Проверить комплект')}<span class="lse-next">${button('issue','Выдать материалы',{primary:true})}</span></div>${state.checked ? `<div class="lse-inline-success">Комплект проверен. ${requiredDocs().some(k => !state.docs.some(d => d.kind === k)) ? 'Есть напоминания о документах — они не блокируют выдачу.' : 'Все документы добавлены.'}</div>` : ''}<p class="lse-helper-line">${state.complex && !state.relatedClosed ? 'Связанная работа 483/4-1-26 ещё в производстве.' : ['completed','without_execution'].includes(state.status) ? 'Работа завершена. Выдача ещё не зарегистрирована.' : 'Работа ещё не завершена.'}</p></div></section><section class="lse-surface"><div class="lse-section-head"><h2>Комплект документов</h2>${button('upload','Добавить файл',{text:true})}</div><ul class="lse-checklist">${requiredDocs().map(k => `<li><span class="${state.docs.some(d => d.kind === k) ? 'lse-checkmark' : 'lse-missingmark'}">${state.docs.some(d => d.kind === k) ? '✓' : '○'}</span>${h(kinds[k])}${k === 'subscription' && state.commission ? ' — на каждого эксперта' : ''}</li>`).join('')}</ul><div class="lse-helper-line">${help('Это напоминания о составе пакета. Не прикреплённые материалы не запрещают завершение работы. Отдельные подписки нужны на каждого участника комиссионной экспертизы.')}</div></section></div>`;
  }
  function historyPage() {return `<section class="lse-surface"><div class="lse-section-head"><h2>История</h2>${help('Каждое действие в этом прототипе добавляется в локальную историю. В рабочем приложении сведения сохраняет сервер.')}</div><ol class="lse-history-list">${state.history.slice().reverse().map(e => `<li><strong>${h(e.title)}</strong><small>${h(e.detail)}</small></li>`).join('')}</ol></section>`;}
  function render() {
    hideTip();
    $('#lse-identity').innerHTML = identity();
    $('#lse-profile-caption').textContent = `${$('#lab-profile').selectedOptions[0].text} · пример прав`;
    $('#lse-notice').hidden = !ui.notice; $('#lse-notice').textContent = ui.notice;
    $('#lse-tabs').innerHTML = Object.entries(tabs).map(([id,label]) => `<button type="button" id="tab-${id}" role="tab" aria-selected="${id === ui.tab}" aria-controls="lse-page" tabindex="${id === ui.tab ? '0' : '-1'}" data-tab="${id}">${label}${id === 'documents' ? ` <span class="lse-muted">${state.docs.length}</span>` : ''}</button>`).join('');
    $('#lse-page').setAttribute('role','tabpanel');$('#lse-page').setAttribute('aria-labelledby',`tab-${ui.tab}`);
    $('#lse-page').innerHTML = ({work,case:casePage,documents:documentsPage,letters:lettersPage,issuance:issuancePage,history:historyPage}[ui.tab])();
  }
  function resultEditor() {
    const d = ui.draft, doc = currentDoc(d.documentId);
    return `<section class="lse-surface"><form id="result-form" class="lse-form"><div class="lse-result-title"><h2>Результат экспертизы</h2>${button('cancel_result','Отменить',{text:true})}${help('Сохраните результат, затем отдельно нажмите «Завершить экспертизу». Документ можно прикрепить позже. Введённые поля сохраняются при выборе и загрузке документа.')}</div><div class="lse-fields">${select('kind','Вид результата',Object.fromEntries((state.category === '6' ? ['research_act'] : ['expert_conclusion','sndz']).map(k => [k,kinds[k]])),d.kind)}${field('completed_on','Дата окончания',d.completed_on,'date')}</div><div class="lse-result-document"><div class="lse-section-head"><h3>${h(kinds[d.kind])}</h3>${help('Можно найти уже зарегистрированный документ или загрузить новый. Коды документов вводить не нужно.')}</div>${doc ? `<div class="lse-selection"><div><strong>${h(doc.title)}</strong><div class="lse-small lse-muted">${h(sourceLabel(doc))}</div></div><div>${button('view','Открыть',{id:doc.id,text:true})}${button('remove_selection','Убрать',{text:true})}</div></div>` : '<p class="lse-small lse-muted">Документ пока не прикреплён</p>'}<div class="lse-search-row">${button('picker','Найти документ')}${button('upload_result',`Загрузить ${d.kind === 'sndz' ? 'СНДЗ' : d.kind === 'research_act' ? 'акт' : 'заключение'}`)}</div></div>${area('note','Примечание',d.note)}${d.kind === 'sndz' ? `<div class="lse-fields">${select('sndz_reason','Причина СНДЗ',{knowledge:'За пределами специальных знаний',materials:'Материалы непригодны / недостаточны',science:'Уровень науки и техники'},d.sndz_reason)}${field('sndz_comment','Пояснение причины',d.sndz_comment)}</div>` : ''}<details class="lse-disclosure"><summary>Статистика и отчётные сведения <span class="lse-summary-meta">Не блокируют завершение</span></summary><div class="lse-disclosure-body"><div class="lse-fields">${field('complexity','Категория сложности',d.complexity,'number','min="1" step="1"')}${field('q','Q — поставленные вопросы',d.q,'number','min="0" step="1"')}${field('r','R — категорические ответы',d.r,'number','min="0" step="1"')}${field('s','S — вероятные ответы',d.s,'number','min="0" step="1"')}${field('t','T — нерешённые вопросы',d.t,'number','min="0" step="1"')}</div><label class="lse-check"><input type="checkbox" name="statistics_complete"${d.statistics_complete ? ' checked' : ''}>Статистика вопросов заполнена ${help('Признак полноты статистики. Не создаёт новых вопросов и не заменяет причину полного СНДЗ.')}</label><label class="lse-check"><input type="checkbox" name="allocations_complete"${d.allocations_complete ? ' checked' : ''}>Распределение нерешённых вопросов заполнено ${help('В рабочей карточке здесь доступно распределение по причинам. В прототипе показан существующий признак полноты; отдельный редактор распределения не моделируется.')}</label></div></details>${area('reason','Основание изменения',d.reason)}<div id="result-error" role="alert" class="lse-inline-error" hidden></div><div class="lse-form-footer"><button type="submit" class="lse-primary">Сохранить результат</button>${button('cancel_result','Отменить',{text:true})}${help('Сейчас сохраняется только результат. Завершение и выдача имеют собственные кнопки и подтверждения.')}</div></form></section>`;
  }
  function captureDraft() {
    const form = $('#result-form'); if (!form || !ui.editing) return;
    const values = new FormData(form);
    for (const [key,value] of values) ui.draft[key] = value;
    ui.draft.statistics_complete = values.has('statistics_complete');ui.draft.allocations_complete = values.has('allocations_complete');
  }
  function showDialog(type, title, body, data = {}, wide = false) {
    hideTip();modal = {type,...data};const dialog = $('#lse-dialog');
    dialog.classList.toggle('lse-dialog-wide',wide);
    dialog.innerHTML = `<div class="lse-dialog-head"><h2 id="lse-dialog-title">${h(title)}</h2><button type="button" data-action="close_dialog" aria-label="Закрыть окно">×</button></div><div class="lse-dialog-body">${body}</div>`;
    if (!dialog.open) dialog.showModal();
  }
  function closeDialog() {hideTip();if ($('#lse-dialog').open) $('#lse-dialog').close();modal = null;}
  function modalForm(type, title, fields, data = {}, submit = 'Сохранить') {
    showDialog(type,title,`<form id="modal-form" class="lse-form">${fields}<div id="modal-error" class="lse-inline-error" role="alert" hidden></div><div class="lse-form-footer"><button type="submit" class="lse-primary">${h(submit)}</button><button type="button" data-action="close_dialog">Отмена</button></div></form>`,data);
  }
  function modalError(message) {const box = $('#modal-error');if (box) {box.textContent = message;box.hidden = false;}}
  function openPicker(query = '') {
    captureDraft();const kind = ui.draft?.kind || state.result?.kind || 'expert_conclusion';
    showDialog('picker','Выбрать документ',`<div class="lse-picker-tools"><span class="lse-muted lse-small">${h(kinds[kind])}</span>${button('upload_result','Добавить новый',{primary:true})}</div><input id="picker-search" type="search" value="${h(query)}" placeholder="Название документа или файла" aria-label="Поиск итогового документа"><div id="picker-list">${pickerList(query,kind)}</div>`,{kind});
  }
  function pickerList(query,kind) {
    const docs = state.docs.filter(d => d.kind === kind && `${d.title} ${d.versions.map(v => v.name).join(' ')}`.toLowerCase().includes(query.toLowerCase()));
    return docs.length ? docs.map(d => docRow(d,true)).join('') : '<p class="lse-empty">Подходящих документов нет. Нажмите «Добавить новый», чтобы загрузить файл.</p>';
  }
  function openUpload({existingId = null,kind = 'other',selectResult = false} = {}) {
    captureDraft();const existing = currentDoc(existingId);
    showDialog('upload',existing ? `Добавить ${existing.versions.length ? 'версию документа' : 'скан постановления'}` : 'Добавить документ',`<form id="upload-form" class="lse-form">${existing ? `<div class="lse-selection"><div><strong>${h(existing.title)}</strong><div class="lse-small lse-muted">Файл добавится к этому документу; новая запись постановления не создаётся.</div></div></div>` : `<div class="lse-fields">${select('kind','Вид документа',selectResult ? {[kind]:kinds[kind]} : kinds,kind)}${field('title','Название',selectResult ? `${kinds[kind]} № ${state.number}` : '')}</div>`}<label class="lse-field"><span>Файл с компьютера ${help('Это локальная демонстрация выбора файла. Файл не отправляется на сервер и не сохраняется в рабочие папки.')}</span><input name="file" id="upload-file" type="file" required></label><div class="lse-picker-tools"><button type="button" data-action="sample_file">Использовать пример PDF</button><span id="upload-file-caption" class="lse-small lse-muted">Файл не выбран</span></div>${area('reason','Основание добавления','')}<details class="lse-disclosure"><summary>Проверка макета</summary><div class="lse-disclosure-body"><label class="lse-check"><input type="checkbox" id="upload-simulate-error">Сымитировать ошибку первой загрузки</label></div></details><div id="upload-progress" class="lse-progress" hidden><progress max="100" value="60" aria-label="Добавление файла"></progress><span>Добавление…</span></div><div id="upload-error" role="alert" class="lse-inline-error" hidden></div><div class="lse-form-footer"><button type="submit" class="lse-primary" id="upload-submit">Добавить документ</button><button type="button" data-action="close_dialog">Отмена</button></div></form>`,{existingId,kind,selectResult,file:null,failed:false});
  }
  function viewDocument(id, index) {
    const doc = currentDoc(id);if (!doc) return;
    const v = doc.versions[index ?? doc.versions.length - 1];
    const content = !v ? '<p class="lse-empty">Зарегистрирован бумажный оригинал. Скан можно добавить кнопкой ниже.</p>' : v.demo ? `<div class="lse-preview-paper"><p>ФГБУ Абаканская ЛСЭ</p><h3>${h(kinds[doc.kind])}</h3><p>№ ${h(state.number)}</p><p>Пример для проверки просмотра документа</p><p class="lse-muted">Условный документ. Не является реальным заключением или постановлением.</p></div>` : /^(image\/(png|jpeg|gif|webp))$/.test(v.type) ? `<img class="lse-preview-image" src="${h(v.url)}" alt="${h(v.name)}">` : `<p class="lse-empty">${h(v.name)}<br>Для этого формата доступно открытие файла.</p>${v.url ? `<a href="${h(v.url)}" target="_blank" rel="noopener">Открыть выбранный файл</a>` : ''}`;
    showDialog('view',doc.title,`<div class="lse-picker-tools"><span class="lse-tag">${h(kinds[doc.kind])}</span>${doc.versions.length ? `<label class="lse-small">Версия <select id="doc-version" aria-label="Версия документа">${doc.versions.map((item,i) => `<option value="${i}"${item === v ? ' selected' : ''}>${i + 1} · ${h(item.name)}</option>`).join('')}</select></label>` : ''}${button(doc.kind === 'basis' ? 'scan' : 'version',doc.versions.length ? 'Добавить версию' : 'Добавить скан',{id:doc.id})}</div>${content}`,{id});
  }
  function confirmAction(type) {
    const labels = {complete:['Завершить экспертизу','Результат сохранён. После подтверждения работа станет завершённой; выдача материалов оформляется отдельно.','Завершить'],reopen:['Вернуть экспертизу в работу','Сохранённые документы и результат останутся в карточке. Событие завершения будет отменено; действие появится в истории.','Вернуть в работу'],return:['Вернуть без исполнения','Это отдельный исход работы. Заключение и полное СНДЗ не создаются. Выдача материалов оформляется отдельно.','Вернуть без исполнения']};
    const [title,text,submit] = labels[type];
    modalForm(type,title,`<p class="lse-small">${text}</p>${type === 'complete' ? `<div class="lse-selection"><div>${h(kinds[state.result.kind])} · ${date(state.result.completed_on)}</div></div>` : field('date',type === 'return' ? 'Дата решения' : 'Дата возврата в работу',today,'date','required')}${reasonField()}`,{},submit);
  }
  function route(tab) {captureDraft();ui.tab = tab;ui.notice = '';render();}
  function handleAction(action, target) {
    if (uploading && action !== 'none') return;
    const reason = denied(action) || target?.dataset.denied;
    if (reason) {toast(reason);return;}
    const id = target?.dataset.id;
    switch (action) {
      case 'close_dialog': closeDialog(); break;
      case 'to_documents': route('documents');break;
      case 'to_issuance': route('issuance');break;
      case 'editresult': captureDraft();ui.draft = ui.draft || structuredClone(state.result || emptyResult(state.category === '6' ? 'research_act' : 'expert_conclusion'));ui.editing = true;ui.tab = 'work';ui.notice = '';render();break;
      case 'cancel_result': ui.editing = false;ui.draft = null;render();break;
      case 'picker': openPicker();break;
      case 'choose_doc': if (ui.editing) ui.draft.documentId = id;else if (state.result) {state.result.documentId = id;state.checked = false;event('Выбран итоговый документ');}closeDialog();render();toast('Документ выбран');break;
      case 'remove_selection': captureDraft();ui.draft.documentId = null;render();break;
      case 'view': viewDocument(id);break;
      case 'upload': openUpload();break;
      case 'scan': case 'version': openUpload({existingId:id});break;
      case 'upload_result': if (!ui.editing && !state.result && rights[ui.profile].includes('result')) {ui.editing = true;ui.tab = 'work';ui.draft = emptyResult(state.category === '6' ? 'research_act' : 'expert_conclusion');render();}openUpload({kind:ui.draft?.kind || state.result?.kind || (state.category === '6' ? 'research_act' : 'expert_conclusion'),selectResult:true});break;
      case 'sample_file': modal.file = {name:'Пример документа.pdf',type:'application/pdf',demo:true};$('#upload-file').required = false;$('#upload-file').value = '';$('#upload-file-caption').textContent = modal.file.name;break;
      case 'complete': case 'reopen': case 'return': confirmAction(action);break;
      case 'assign': modalForm('assign','Редактировать исполнителей',`<div class="lse-fields"><label class="lse-field lse-wide"><span>Эксперты по специальности ${h(state.specialty)}</span>${['Лалетина О.В.','Второй эксперт (пример)'].map(name => `<label class="lse-check"><input type="checkbox" name="employees" value="${h(name)}"${state.employees.includes(name) ? ' checked' : ''}>${h(name)}</label>`).join('')}<span class="lse-check lse-muted"><input type="checkbox" disabled>Стажёр по специальности (пример) ${help('Стажировка учитывается только как обучение. Назначать на экспертизу по неподтверждённой специальности нельзя.')}</span></label></div>${reasonField()}`);break;
      case 'editcase': modalForm('editcase','Редактировать сведения дела',`<div class="lse-fields">${field('authority','Назначивший орган',state.case.authority)}${field('official','Должностное лицо',state.case.official)}${field('contact','Контакт',state.case.contact)}${field('case_number','Номер дела',state.case.case_number)}${area('description','Описание',state.case.description)}${area('basis_text','Основание',state.case.basis_text)}${area('inventory','Опись материалов',state.case.inventory)}${area('questions_text','Вопросы',state.case.questions_text)}</div>${reasonField()}`);break;
      case 'classification': modalForm('classification','Редактировать характер экспертизы',`${select('classification','Характер назначения',{primary:'Первичная',additional:'Дополнительная',repeated:'Повторная'},state.classification)}<label class="lse-check"><input type="checkbox" name="commission"${state.commission ? ' checked' : ''}>Комиссионная ${help('Комиссионная может быть первичной, дополнительной или повторной. Несколько экспертов работают под одним номером.')}</label><p class="lse-helper-line">${state.complex ? 'Работа уже входит в комплекс из отдельных номеров.' : 'Связь с другими номерами комплексной работы в этом макете показана отдельным сценарием.'}</p>${reasonField()}`);break;
      case 'deadline': modalForm('deadline','Редактировать срок',`<div class="lse-fields">${select('event','Событие',{initial:'Установить срок',request:'Запросить продление',agreement:'Согласовать новый срок'},'initial')}${field('date','Дата события',today,'date','required')}${field('deadline','Срок выполнения',state.deadline,'date','required')}</div>${reasonField()}`);break;
      case 'pause': modalForm('pause','Приостановить экспертизу',`${field('date','Дата приостановки',today,'date','required')}${reasonField()}`,{},'Приостановить');break;
      case 'resume': modalForm('resume','Возобновить экспертизу',`${field('date','Дата возобновления',today,'date','required')}${reasonField()}`,{},'Возобновить');break;
      case 'letter': modalForm('letter','Добавить письмо',`<div class="lse-fields">${select('direction','Направление',{incoming:'Входящее',outgoing:'Исходящее'},'incoming')}${field('date','Дата письма',today,'date','required')}${field('number','Номер письма')}${field('recipient','Отправитель / получатель')}${field('subject','Тема','','text','required')}${area('body','Содержание')}</div><p class="lse-helper-line">${help('В этом макете создаётся локальная запись переписки. Письмо никуда не отправляется. Полный цикл регистрации и ответов проверим на рабочем стенде после согласования карточки.')}</p>`);break;
      case 'view_letter': {const letter = state.letters.find(l => l.id === id);showDialog('letterview',letter.subject,`<p class="lse-contact-line">${h(letter.direction)} · ${date(letter.date)} · ${h(letter.number)}</p><p class="lse-contact-line">${h(letter.recipient)}</p><p class="lse-preserve">${h(letter.body || 'Текст не добавлен')}</p>`);break;}
      case 'prepare': state.checked = false;event('Состав материалов для выдачи сохранён');notice('Состав материалов сохранён в прототипе.');break;
      case 'check': state.checked = true;event('Комплект для выдачи проверен');notice('Комплект проверен. Отсутствующие файлы отмечены как напоминания.');break;
      case 'issue': modalForm('issue','Выдать материалы',`<div class="lse-fields">${field('date','Дата выдачи',today,'date','required')}${select('method','Способ',{personal:'Лично',post:'Почтой',courier:'Курьером'},'personal')}${field('recipient','Получатель','','text','required')}${field('basis','Основание получения')}${field('tracking','Трек-номер / отметка')}${area('comment','Примечание')}</div>${reasonField()}`,{},'Подтвердить выдачу');break;
      case 'related': showDialog('related','Связанная работа 483/4-1-26',`<dl class="lse-facts"><div><dt>Специальность</dt><dd>18.1</dd></div><div><dt>Состояние</dt><dd>${state.relatedClosed ? 'Завершена' : 'В производстве'}</dd></div></dl><div class="lse-form-footer">${button('finish_related','Сымитировать завершение связанной работы',{reason:!rights[ui.profile].includes('complete') ? 'В этом профиле нет права завершать экспертизы.' : ''})}${help('Только инструмент проверки макета. В рабочей АИС связанная работа завершается в собственной карточке.')}</div>`);break;
      case 'finish_related': if (!rights[ui.profile].includes('complete')) return;state.relatedClosed = true;state.checked = false;event('Связанная работа завершена (сценарий макета)');closeDialog();render();break;
    }
  }
  function submitResult() {
    captureDraft();const reason = denied('save_result');if (reason) {toast(reason);return;}
    const d = ui.draft;
    if (d.completed_on && d.completed_on < state.received) return resultError('Дата окончания раньше поступления. Исправьте дату или оставьте её пустой для черновика.');
    if (['q','r','s','t'].some(k => d[k] !== '' && (!Number.isInteger(Number(d[k])) || Number(d[k]) < 0))) return resultError('В статистике допустимы целые неотрицательные числа.');
    if (d.complexity !== '' && (!Number.isInteger(Number(d.complexity)) || Number(d.complexity) < 1)) return resultError('Категория сложности — целое число не меньше 1.');
    const parts = ['r','s','t'], total = parts.reduce((sum,key) => sum + (d[key] === '' ? 0 : Number(d[key])),0);
    if (d.q !== '' && (total > Number(d.q) || parts.every(key => d[key] !== '') && total !== Number(d.q))) return resultError('Проверьте равенство Q = R + S + T: поставленные вопросы равны сумме категорических, вероятных и нерешённых.');
    if (d.statistics_complete && ['q','r','s','t'].some(key => d[key] === '')) return resultError('Для отметки полноты статистики заполните Q, R, S и T, включая известные нули. Без этой отметки поля можно оставить пустыми.');
    state.result = structuredClone(d);state.checked = false;ui.editing = false;ui.draft = null;event('Результат сохранён',`${kinds[d.kind]} · работа ${state.status === 'completed' ? 'остаётся завершённой' : 'продолжается'}`);notice('Результат сохранён. Завершение — отдельная кнопка.');
  }
  function resultError(message) {$('#result-error').textContent = message;$('#result-error').hidden = false;}
  function submitModal(form) {
    const type = modal.type, values = new FormData(form), get = name => String(values.get(name) || '').trim();
    const action = {assign:'assign',editcase:'editcase',classification:'classification',deadline:'deadline',pause:'pause',resume:'resume',complete:'complete',reopen:'reopen',return:'return',letter:'letter',issue:'issue'}[type];
    const refusal = denied(action);if (refusal) return modalError(refusal);
    if (['complete','reopen','return','pause','resume','assign','editcase','classification','deadline','issue'].includes(type) && !get('reason')) return modalError('Укажите основание изменения.');
    if (get('date') && get('date') < state.received) return modalError('Дата события раньше поступления. Проверьте дату.');
    if (type === 'assign') {
      const employees = values.getAll('employees');if (!employees.length) return modalError('Выберите хотя бы одного эксперта.');if (state.commission && employees.length < 2) return modalError('Для комиссионной работы выберите минимум двух экспертов.');
      state.employees = employees;event('Исполнители изменены',get('reason'));
    } else if (type === 'editcase') {
      for (const key of Object.keys(state.case)) state.case[key] = get(key);
      event('Сведения о деле изменены',get('reason'));
    } else if (type === 'classification') {
      state.classification = get('classification');state.commission = values.has('commission');event('Характер экспертизы изменён',get('reason'));
    } else if (type === 'deadline') {
      if (get('event') !== 'request') state.deadline = get('deadline');event(get('event') === 'request' ? 'Запрошено продление срока' : 'Срок выполнения изменён',`${date(get('deadline'))} · ${get('reason')}`);
    } else if (type === 'pause') {
      state.status = 'suspended';state.pause = {date:get('date'),reason:get('reason')};event('Экспертиза приостановлена',get('reason'));
    } else if (type === 'resume') {
      if (state.pause && get('date') < state.pause.date) return modalError('Возобновление не может быть раньше приостановки.');state.status = 'in_progress';delete state.pause;event('Экспертиза возобновлена',get('reason'));
    } else if (type === 'complete') {
      if (state.result.completed_on < state.received) return modalError('Дата окончания раньше поступления.');state.status = 'completed';state.checked = false;event('Экспертиза завершена',get('reason'));
    } else if (type === 'return') {
      state.status = 'without_execution';state.checked = false;event('Возвращена без исполнения',get('reason'));
    } else if (type === 'reopen') {
      state.status = state.pause ? 'suspended' : 'in_progress';state.checked = false;event('Экспертиза возвращена в работу',get('reason'));
    } else if (type === 'letter') {
      state.letters.push({id:uid('letter'),date:get('date'),direction:get('direction') === 'incoming' ? 'Входящее' : 'Исходящее',number:get('number'),subject:get('subject'),recipient:get('recipient'),body:get('body')});event('Добавлена запись переписки',get('subject'));
    } else if (type === 'issue') {
      if (state.result?.completed_on && get('date') < state.result.completed_on) return modalError('Выдача не может быть раньше окончания работы.');state.issued = {date:get('date'),recipient:get('recipient'),method:{personal:'Лично',post:'Почтой',courier:'Курьером'}[get('method')]};event('Материалы выданы',`${get('recipient')} · ${get('reason')}`);
    }
    closeDialog();notice(type === 'complete' ? 'Экспертиза завершена. Материалы ещё не выданы.' : type === 'issue' ? 'Выдача зарегистрирована в прототипе.' : 'Изменения сохранены в прототипе.');
  }
  async function submitUpload(form) {
    const refusal = denied('upload');if (refusal) {toast(refusal);return;}
    const m = modal, values = new FormData(form);
    const chosen = m.file || $('#upload-file').files[0];
    if (!chosen) return;
    uploading = true;$('#upload-progress').hidden = false;$('#upload-error').hidden = true;
    for (const el of form.elements) el.disabled = true;
    await new Promise(resolve => setTimeout(resolve,650));
    if ($('#upload-simulate-error').checked && !m.failed) {
      m.failed = true;uploading = false;$('#upload-progress').hidden = true;
      for (const el of form.elements) el.disabled = false;
      $('#upload-error').textContent = 'Тестовая ошибка: файл не добавлен. Выбранный файл и заполненные поля сохранены. Нажмите «Повторить». Это не реальный сбой сервера.';$('#upload-error').hidden = false;$('#upload-submit').textContent = 'Повторить';return;
    }
    const version = {id:uid('v'),name:chosen.name,type:chosen.type,demo:!!chosen.demo};
    if (!chosen.demo) {version.url = URL.createObjectURL(chosen);urls.add(version.url);}
    let doc = currentDoc(m.existingId);
    if (doc) {doc.versions.push(version);doc.source = 'copy';}
    else {doc = {id:uid('doc'),kind:String(values.get('kind') || m.kind),title:String(values.get('title') || '').trim() || chosen.name,source:'copy',versions:[version]};state.docs.push(doc);}
    if (m.selectResult) {
      if (ui.editing) ui.draft.documentId = doc.id;
      else if (state.result) state.result.documentId = doc.id;
    }
    state.checked = false;event(m.existingId ? 'Добавлена версия документа' : 'Добавлен документ',doc.title);uploading = false;closeDialog();render();toast(m.selectResult && !state.result && !ui.editing ? 'Документ добавлен в дело. Выберите его при добавлении результата.' : m.existingId ? 'Скан добавлен к существующему документу' : 'Документ добавлен');
  }
  function showTip(anchor,pinned = false) {
    clearTimeout(tipTimer);if (tipAnchor && tipAnchor !== anchor) tipAnchor.removeAttribute('aria-describedby');
    tipAnchor = anchor;tipPinned = pinned;const tip = $('#lse-tooltip');tip.textContent = anchor.dataset.help;tip.hidden = false;anchor.setAttribute('aria-describedby','lse-tooltip');
    // Native dialogs occupy the top layer. The help must share that layer.
    const parent = anchor.closest('dialog') || document.body;if (tip.parentElement !== parent) parent.append(tip);
    const r = anchor.getBoundingClientRect(), t = tip.getBoundingClientRect();
    tip.style.left = `${Math.max(12,Math.min(r.left,innerWidth - t.width - 12))}px`;
    tip.style.top = `${Math.max(12,r.bottom + t.height + 10 < innerHeight ? r.bottom + 7 : r.top - t.height - 7)}px`;
  }
  function hideTip() {clearTimeout(tipTimer);if (tipAnchor) tipAnchor.removeAttribute('aria-describedby');tipAnchor = null;tipPinned = false;const tip = $('#lse-tooltip');tip.hidden = true;if (tip.parentElement !== document.body) document.body.append(tip);}
  expansion = window.createLsePrototypeExpansion({
    get state(){return state;},get ui(){return ui;},get modal(){return modal;},get uploading(){return uploading;},set uploading(value){uploading=value;},
    $,h,date,today,uid,help,button,field,area,select,reasonField,kinds,tabs,scenarios,rights,rightNames,urls,
    currentDoc,demoDoc,event,toast,notice,captureDraft,emptyResult,requiredDocs,
    core:{work,casePage,documentsPage,lettersPage,issuancePage,historyPage,render,denied,handleAction,submitModal,submitResult,submitUpload,openUpload,openPicker,viewDocument,closeDialog,showDialog,modalForm,route},
    showDialog,modalForm,modalError,resultError
  });
  ({work,casePage,documentsPage,lettersPage,issuancePage,historyPage,render,denied,handleAction,submitModal,submitResult,submitUpload,openUpload,openPicker,viewDocument,closeDialog,route} = expansion);
  delete window.createLsePrototypeExpansion;
  document.addEventListener('click', e => {
    const hint = e.target.closest('[data-help]');
    if (hint) {e.preventDefault();e.stopPropagation();if (tipAnchor === hint && tipPinned) hideTip();else showTip(hint,true);return;}
    hideTip();
    const command = e.target.closest('[data-action]');if (command) {e.preventDefault();handleAction(command.dataset.action,command);return;}
    const tab = e.target.closest('[data-tab]');if (tab) {route(tab.dataset.tab);$(`#tab-${ui.tab}`).focus();return;}
    const nav = e.target.closest('[data-nav]');if (nav) {if (nav.dataset.nav.startsWith('info:')) showDialog('scope',nav.textContent.trim(),'<p class="lse-small">Этот раздел находится за пределами теста карточки. Здесь проверяем работу с экспертизой: дело, документы, результат, переписку и выдачу. Рабочий стенд откроем после утверждения макета.</p>');else route(nav.dataset.nav);}
  });
  document.addEventListener('submit', e => {e.preventDefault();if (e.target.id === 'result-form') submitResult();else if (e.target.id === 'modal-form') submitModal(e.target);else if (e.target.id === 'upload-form') submitUpload(e.target);});
  document.addEventListener('input', e => {
    if (e.target.closest('#result-form')) captureDraft();
    if (e.target.id === 'doc-search') $('#doc-list').innerHTML = state.docs.filter(d => `${d.title} ${d.versions.map(v => v.name).join(' ')}`.toLowerCase().includes(e.target.value.toLowerCase())).map(d => docRow(d)).join('') || '<p class="lse-empty">Документы не найдены</p>';
    if (e.target.id === 'picker-search') $('#picker-list').innerHTML = pickerList(e.target.value,modal.kind);
    if (e.target.id === 'issue-materials') {state.materials = e.target.value;state.checked = false;updateIssueButtons();}
  });
  function updateIssueButtons() {for (const el of document.querySelectorAll('[data-action="check"],[data-action="issue"]')) {const wrapper = el.parentElement;wrapper.outerHTML = button(el.dataset.action,el.textContent,{primary:el.dataset.action === 'issue'});}const saved = $('.lse-inline-success');if (saved) saved.hidden = !state.checked;}
  document.addEventListener('change', e => {
    if (e.target.name === 'kind' && e.target.closest('#result-form')) {captureDraft();const selected = currentDoc(ui.draft.documentId);if (selected && selected.kind !== ui.draft.kind) ui.draft.documentId = null;render();}
    if (e.target.id === 'upload-file' && e.target.files[0]) {modal.file = null;$('#upload-file-caption').textContent = e.target.files[0].name;e.target.required = true;}
    if (e.target.id === 'doc-version') viewDocument(modal.id,Number(e.target.value));
    if (e.target.id === 'issue-paid') {state.paid = e.target.checked;state.checked = false;render();}
  });
  document.addEventListener('pointerover',e => {const anchor = e.target.closest('[data-help]');if (anchor && !tipPinned) showTip(anchor);if (e.target.closest('#lse-tooltip')) clearTimeout(tipTimer);});
  document.addEventListener('pointerout',e => {if ((e.target.closest('[data-help]') || e.target.closest('#lse-tooltip')) && !tipPinned) tipTimer = setTimeout(hideTip,160);});
  document.addEventListener('focusin',e => {const anchor = e.target.closest('[data-help]');if (anchor) showTip(anchor);});
  document.addEventListener('focusout',e => {if (e.target.closest('[data-help]') && !tipPinned) tipTimer = setTimeout(hideTip,160);});
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && tipAnchor) {e.preventDefault();e.stopPropagation();hideTip();return;}
    const tab = e.target.closest('[data-tab]');if (tab && ['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {e.preventDefault();const ids = Object.keys(tabs),i = ids.indexOf(ui.tab);route(ids[e.key === 'Home' ? 0 : e.key === 'End' ? ids.length-1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + ids.length) % ids.length]);$(`#tab-${ui.tab}`).focus();}
  },true);
  $('#lse-dialog').addEventListener('cancel',e => {if (uploading) e.preventDefault();else {modal = null;hideTip();}});
  $('#lab-scenario').innerHTML = Object.entries(scenarios).map(([id,label]) => `<option value="${id}">${label}</option>`).join('');
  $('#lab-scenario').addEventListener('change',e => {if (uploading) {e.target.value = state.scenario;return;}reset(e.target.value);});
  $('#lab-profile').addEventListener('change',e => {if (uploading) {e.target.value = ui.profile;return;}captureDraft();ui.profile = e.target.value;if (ui.editing && denied('save_result')) {ui.editing = false;ui.draft = null;}closeDialog();render();});
  $('#lab-reset').addEventListener('click',() => reset(state.scenario));
  $('#sidebar-toggle').addEventListener('click',() => {const shell = $('.lse-shell');if (innerWidth <= 800) shell.classList.toggle('lse-expanded-mobile');else shell.classList.toggle('lse-collapsed');const collapsed = innerWidth <= 800 ? !shell.classList.contains('lse-expanded-mobile') : shell.classList.contains('lse-collapsed');$('#sidebar-toggle').setAttribute('aria-expanded',String(!collapsed));$('#sidebar-toggle').setAttribute('aria-label',collapsed ? 'Развернуть меню' : 'Свернуть меню');});
  window.addEventListener('resize',hideTip);window.addEventListener('scroll',hideTip,{passive:true});
  window.addEventListener('beforeunload',() => {for (const url of urls) URL.revokeObjectURL(url);});
  reset();
})();
