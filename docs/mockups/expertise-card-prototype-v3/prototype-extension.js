/* Extra card scenarios for the isolated prototype. No network or persistence. */
window.createLsePrototypeExpansion = function (a) {
  'use strict';
  const {$,h,date,today,uid,help,button,field,area,select,reasonField,core} = a;
  const S=()=>a.state, U=()=>a.ui, M=()=>a.modal;
  const yesNo={'':'Неизвестно',true:'Да',false:'Нет'};
  const delays={research_complexity:'Сложность проведённых исследований',large_material_volume:'Исследование значительного объёма материалов',expert_workload:'Загруженность экспертов — очередность проведения экспертиз',long_research_methods:'Длительные методики исследований',appointing_party_deadline:'Срок назначившего органа / лица',other:'Иные причины'};
  const unresolved={methods_insufficient:'Недостаточная разработанность методик',materials_insufficient:'Недостаточность представленных материалов',objects_uninformative:'Недостаточная информативность объектов исследования',other:'Иные'};
  const returns={no_technical_facilities:'Отсутствие материально-технической базы',no_required_specialist:'Отсутствие эксперта конкретной специальности',no_special_conditions:'Отсутствие специальных условий',appointing_party_request:'По запросу назначившего органа / лица',other:'Иные причины'};
  const authorities={'':'Не определён',court:'Суд',investigation:'Следственные органы СК РФ',mvd:'Органы внутренних дел',other:'Иной орган / заявитель'};
  const specs={'1.1':'1.1 · почерковедение','3.1':'3.1 · техническая экспертиза документов','13.1':'13.1','16.1':'16.1','16.2':'16.2','18.1':'18.1','19.1':'19.1'};
  const extraPermissions={reassign:'assign',timing:'case',historical:'closed_correct',activate:'case',complex:'case',source:'documents',attach_issue:'issue_prepare',edit_package_item:'issue_prepare',remove_package_item:'issue_prepare',package_edit:'issue_prepare',letter_attachment:'letters',letter_edit:'letters',letter_reply:'letters',letter_register:'letter_register',letter_send:'letter_send',letter_receive:'letter_register',letter_deliver:'letter_register',letter_control:'letter_control',letter_assign:'letter_control',letter_deadline:'letter_control',letter_close:'letter_control',letter_reopen:'letter_control'};
  Object.assign(extraPermissions,{folder_upload:'documents',source_document:'documents',new_ref:'documents',reference_new:'documents'});
  extraPermissions.activate='history_activate';a.rights.full.push('history_activate');a.rightNames.history_activate='Подтверждать историческую работу для нового учёта';
  Object.assign(a.scenarios,{longwork:'Срок > 30 дней',construction:'16.1 · самовольное строение',historical:'Старая работа · новый учёт',historical_closed:'Старая завершённая работа',repeated:'Повторная / дополнительная',mixed_questions:'Нерешённые вопросы T',document_sources:'Документы: папка / ссылка / оригинал'});
  const tabOrder={work:a.tabs.work,case:a.tabs.case,production:'Сроки',documents:a.tabs.documents,letters:a.tabs.letters,issuance:a.tabs.issuance,history:a.tabs.history};
  for(const key of Object.keys(a.tabs))delete a.tabs[key];Object.assign(a.tabs,tabOrder);
  Object.assign(a.kinds,{deadline_request:'Ходатайство о продлении',deadline_agreement:'Согласование срока',return_decision:'Решение о возврате',letter:'Документ переписки',case_material:'Материал дела'});
  Object.assign(a.rightNames,{letter_register:'Регистрировать переписку',letter_send:'Записывать отправку',letter_control:'Управлять контролем переписки'});
  a.rights.full.push('letter_register','letter_send','letter_control');a.rights.clerk.push('letter_register','letter_send','letter_control');
  let docContext=null, discard=null, revisionAttempt=null;
  const values=form=>Object.fromEntries(new FormData(form));
  const checkbox=(name,label,checked=false,tip='')=>`<label class="lse-check"><input name="${h(name)}" type="checkbox"${checked?' checked':''}>${h(label)}${tip?help(tip):''}</label>`;
  const section=(title,body,actions='',feature='')=>`<section class="lse-surface"${feature?` data-feature="${feature}"`:''}><div class="lse-section-head"><h2>${h(title)}</h2>${actions}</div>${body}</section>`;
  const disclosure=(title,body,meta='',feature='')=>`<details class="lse-disclosure"${feature?` data-feature="${feature}"`:''}><summary>${h(title)}${meta?`<span class="lse-summary-meta">${h(meta)}</span>`:''}</summary><div class="lse-disclosure-body">${body}</div></details>`;
  const table=(head,rows)=>`<div class="lse-table-wrap"><table class="lse-table"><thead><tr>${head.map(x=>`<th>${h(x)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(x=>`<td>${x}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${head.length}" class="lse-muted">Записей пока нет</td></tr>`}</tbody></table></div>`;
  const detailDoc=id=>{const d=a.currentDoc(id);return d?button('view',d.title,{id,text:true}):'<span class="lse-muted">Не прикреплён</span>';};
  function seed(scenario) {
    docContext=null;viewReturn=null;discard=null;releaseAttempt();
    const s=S();s.version=1;s.assignments=s.employees.map(name=>({id:uid('assignment'),name,started:s.received,ended:null,reason:'Назначение в условном примере'}));
    s.pauses=s.pause?[{start:s.pause.date,end:null,reason:s.pause.reason}]:[];s.deadlineEvents=[];
    s.timing={reasons:[],primary:'',complete:false,notification_sent:'',notification_on:'',notification_document:'',extension_requested:'',request_on:'',request_document:'',deadline_breached:'',breach_basis:'',breach_document:''};
    s.previous=[];s.previousComplete=false;s.groupTitle='';s.groupWorks=s.complex?[{number:'483/4-1-26',spec:'18.1',closed:false}]:[];
    s.case.authority_type='mvd';s.case.decree=false;s.case.decree_basis='';s.case.decree_document='';
    s.packageItems=[];s.packageNote='';s.billing={[s.number]:false};s.packageChecks=[];s.corrections=[];s.resultRevisions=[];s.closures=[];s.source=null;
    s.letterKinds={request:'Запрос',reply:'Ответ на запрос',information:'Информационное письмо',cover:'Сопроводительное письмо',other:'Иная переписка'};
    if(scenario==='longwork') {s.received='2026-08-10';s.deadline='2026-09-10';s.assignments.forEach(x=>x.started=s.received);s.pauses=[{start:'2026-09-01',end:'2026-09-11',reason:'Дополнительные материалы'}];}
    if(scenario==='construction') {s.specialty='16.1';s.department='3';s.number='482/3-2-26';s.category='2';s.case.authority_type='court';s.case.authority='Абаканский городской суд (пример)';s.case.decree=true;s.case.decree_basis='Проверка признака самовольного строения, условный пример';s.billing={[s.number]:false};}
    if(scenario==='repeated'){s.classification='repeated';s.previous=[{key:uid('prev'),reference:'Предыдущее заключение № 15 (пример)',organization:'Учреждение из постановления (пример)',group:'ministry',same:'true',confirms:'',document:''}];}
    if(scenario==='mixed_questions'){s.result={...a.emptyResult(),completed_on:today,q:'10',r:'6',s:'2',t:'2',statistics_complete:true,allocations_complete:false,allocations:[],reason:'Условный результат'};}
    if(scenario==='document_sources') {
      const original=a.demoDoc('subscription','Подписка эксперта · бумажный оригинал');
      const linked=a.demoDoc('other','Документ по ссылке');linked.source='link';linked.source_url='https://example.invalid/document.pdf';
      const folder=a.demoDoc('case_material','Фото из выбранной папки',true);folder.relativePath='482_4-1-26/Материалы/фото.pdf';
      s.docs.push(original,linked,folder);
    }
    if(['historical','historical_closed'].includes(scenario)) {
      s.number='1/1-1-26';s.department='1';s.received='2026-01-23';s.employees=[];s.assignments=[];
      const closed=scenario==='historical_closed';s.status=closed?'completed':'in_progress';
      s.source={operational:false,historical_number:'2114/10-1-25 от 17.06.2025',number:s.number,department:'1',received:s.received,completed:closed?'2026-02-18':'',issued:closed?'2026-02-19':'',executor:'Арыштаев А.С. (пример источника)',row:2,observed:'29.10.2026',result:closed?{...a.emptyResult(),completed_on:'2026-02-18',q:'2',r:'2',s:'0',t:'0',statistics_complete:true}:null,pausesComplete:false};
      s.billing={[s.number]:false};
      s.source.raw={case:structuredClone(s.case),specialty:s.specialty,category:s.category,status:s.status,amount:null};
      s.source.snapshot=structuredClone(s.source);
    }
  }
  function permitted(action){const right=extraPermissions[action];return !right||a.rights[U().profile].includes(right);}
  function denied(action) {
    const s=S(),right=extraPermissions[action];
    if(right&&!permitted(action))return `В этом профиле нет права «${a.rightNames[right]||right}». Действие доступно через роль сотрудника.`;
    if(s.source&&!s.source.operational&&['assign','reassign','pause','resume','deadline','complete','return','reopen'].includes(action))return 'Историческая работа ещё не подтверждена для нового учёта. Сведения источника доступны отдельно.';
    if(s.source&&!s.source.operational&&(['check','issue'].includes(action)||action==='editresult'&&!['completed','without_execution'].includes(s.status)))return 'Сначала подтвердите историческую работу для нового учёта. Исходный журнал не заменяет рабочие события.';
    if(action==='activate'&&(!s.source||s.source.operational))return 'Работа уже ведётся в новом учёте.';
    if(action==='historical'&&(!s.source||s.source.operational))return 'Уточнение предназначено для исторического результата; итог нового учёта редактируется отдельно.';
    if(['package_edit','attach_issue','edit_package_item','remove_package_item'].includes(action)&&s.issued)return 'Выдача уже зарегистрирована; комплект сохраняется как история передачи.';
    if(['check','issue'].includes(action)&&packageWorks().some(w=>s.billing[w.number]===undefined||s.billing[w.number]===null))return 'Уточните платность каждой работы комплекта.';
    if(['reassign','complex'].includes(action)&&['completed','without_execution'].includes(s.status))return 'Работа завершена. Верните её в работу для изменения процесса.';
    if(action==='letter_send'&&M()?.letter?.directionCode==='incoming')return 'Для входящего письма фиксируется получение. Отправку фиксируют для исходящего.';
    if(action==='letter_edit'&&M()?.letter?.registration)return 'Зарегистрированное содержание заморожено. Приложения, ответы и факты переписки учитываются отдельными действиями.';
    return core.denied(action);
  }
  function docSlot(name,label,id='',allowed=null) {
    const d=a.currentDoc(id),allowedText=allowed?.join(',')||'';
    return `<div class="lse-doc-slot" data-doc-slot="${h(name)}" data-doc-label="${h(label)}" data-doc-kinds="${h(allowedText)}"><input type="hidden" name="${h(name)}" value="${h(id)}"><div class="lse-section-head"><h3>${h(label)}</h3></div>${d?`<div class="lse-selection"><div>${h(d.title)}</div>${button('view','Открыть',{id:d.id,text:true})}</div>`:'<p class="lse-inline-note">Не выбран</p>'}<div class="lse-picker-tools">${button('pick_ref','Найти документ',{id:name})}${button('new_ref','Добавить новый',{id:name})}${d?button('clear_ref','Убрать',{id:name,text:true}):''}</div></div>`;
  }
  function formSnapshot() {
    const dialog=$('#lse-dialog');return {modal:{...M()},html:dialog.innerHTML,fields:[...dialog.querySelectorAll('input,textarea,select')].map(el=>({name:el.name,value:el.value,checked:el.checked})),wide:dialog.classList.contains('lse-dialog-wide')};
  }
  function restoreSnapshot(snapshot) {
    const title=new DOMParser().parseFromString(snapshot.html,'text/html').querySelector('#lse-dialog-title')?.textContent||'Редактирование';
    const body=new DOMParser().parseFromString(snapshot.html,'text/html').querySelector('.lse-dialog-body')?.innerHTML||'';
    a.showDialog(snapshot.modal.type,title,body,snapshot.modal,snapshot.wide);
    for(const value of snapshot.fields){const el=[...$('#lse-dialog').querySelectorAll('input,textarea,select')].find(x=>x.name===value.name);if(el){el.value=value.value;if(el.type==='checkbox'||el.type==='radio')el.checked=value.checked;}}
  }
  function setSlot(id) {const ctx=docContext;docContext=null;restoreSnapshot(ctx.snapshot);const slot=[...$('#lse-dialog').querySelectorAll('[data-doc-slot]')].find(x=>x.dataset.docSlot===ctx.name);if(slot)slot.outerHTML=docSlot(ctx.name,ctx.label,id,ctx.allowed);}
  function pickReference(name,newDocument=false) {
    const slot=[...$('#lse-dialog').querySelectorAll('[data-doc-slot]')].find(x=>x.dataset.docSlot===name);if(!slot)return;
    docContext={snapshot:formSnapshot(),name,label:slot.dataset.docLabel,allowed:slot.dataset.docKinds?slot.dataset.docKinds.split(','):null};
    if(newDocument)openUpload({kind:docContext.allowed?.[0]||'other'});else referencePicker();
  }
  function referencePicker() {a.showDialog('reference_picker','Выбрать документ',`<div class="lse-picker-tools">${button('reference_new','Добавить новый',{primary:true})}</div><input id="ref-search" type="search" placeholder="Поиск по названию и файлу" aria-label="Поиск документа для поля"><div id="ref-list">${referenceRows('')}</div>`);}
  function referenceRows(query) {const docs=S().docs.filter(d=>(!docContext.allowed||docContext.allowed.includes(d.kind))&&`${d.title} ${d.versions.map(v=>v.name).join(' ')}`.toLowerCase().includes(query.toLowerCase()));return docs.map(d=>`<div class="lse-doc-row"><span class="lse-doc-icon">▤</span><div>${h(d.title)}<div class="lse-doc-meta">${h(a.kinds[d.kind])}</div></div>${button('reference_choose','Выбрать',{id:d.id})}</div>`).join('')||'<p class="lse-empty">Подходящих документов нет. Можно добавить новый.</p>';}
  function extendedForm(type,title,body,data={},submit='Сохранить') {a.modalForm(type,title,body,data,submit);initializeSelects($('#lse-dialog'));M().initial=JSON.stringify(values($('#modal-form')));}
  function assignmentForm(reassign=false) {
    const s=S();extendedForm(reassign?'reassign':'assign',reassign?'Перепоручить экспертизу':'Редактировать состав исполнителей',`<p class="lse-helper-line">${help('Квалификация проверяется по специальности работы. Стажёр участвует только в обучении. Номер при перепоручении сохраняется. Состав комиссии — минимум два эксперта, единоличная работа — один.')}</p><div class="lse-candidate-list">${['Лалетина О.В.','Второй эксперт (пример)'].map(name=>checkbox('employees',name,s.employees.includes(name)).replace('type="checkbox"',`type="checkbox" value="${h(name)}"`)).join('')}<div class="lse-check lse-muted"><input type="checkbox" disabled>Стажёр по ${h(s.specialty)} ${help('Специальность ещё не получена. Назначение недоступно.')}</div><div class="lse-check lse-muted"><input type="checkbox" disabled>Эксперт другой специальности ${help('Нет полученной специальности '+s.specialty+'.')}</div></div>${reasonField()}`,{},reassign?'Сохранить перепоручение':'Сохранить состав');
  }
  function work() {
    let html=core.work(),s=S();
    if(!U().editing)html=html.replace(button('assign','Редактировать'),`${button('assign','Редактировать')}${button('reassign','Перепоручить')}`);
    const history=table(['Эксперт','Назначен','Окончание','Основание'],s.assignments.map(x=>[h(x.name),date(x.started),x.ended?date(x.ended):'Действует',h(x.reason)]));
    html+=disclosure('История назначений',history,`${s.assignments.length} записей`,'assignments');
    if(s.result&&!U().editing)html+=disclosure('Показатели результата',table(['Показатель','Значение'],[['Сложность',h(s.result.complexity||'Неизвестно')],['Q — поставленные вопросы',h(s.result.q||'Неизвестно')],['R — категорические ответы',h(s.result.r||'Неизвестно')],['S — вероятные ответы',h(s.result.s||'Неизвестно')],['T — нерешённые вопросы',h(s.result.t||'Неизвестно')],['Примечание',h(s.result.note||'Не указано')]])+table(['Причина T','Количество','Пояснение'],(s.result.allocations||[]).map(x=>[h(unresolved[x.reason]),h(x.count),h(x.comment)])),'Q / R / S / T','result-statistics');
    if(s.status==='without_execution')html+=disclosure('Решение без исполнения',table(['Сведения','Значение'],[['Дата решения',date(s.closures.at(-1)?.date||s.source?.completed)],['Причина',h(returns[s.returnReason]||'Не уточнена')],['Пояснение',h(s.returnComment||'Не указано')],['Документ',detailDoc(s.returnDocument)]]),'Отдельный исход работы','return-details');
    if(s.source)html=sourceBanner()+html;
    if(U().editing) {
      html=html.replace('<label class="lse-check"><input type="checkbox" name="allocations_complete"',`<div data-feature="allocations"><div id="result-allocations">${(U().draft.allocations||[]).map(x=>allocationRow(x)).join('')}</div>${button('add_allocation','Добавить причину нерешённых вопросов')}</div><label class="lse-check"><input type="checkbox" name="allocations_complete"`);
    }
    return html;
  }
  function counts() {
    const s=S(),closed=['completed','without_execution'].includes(s.status),end=closed?s.closures.at(-1)?.date||s.result?.completed_on||s.source?.completed||null:today;
    if(!end)return {calendar:'Неизвестно',paused:'Неизвестно',active:'Неизвестно',end:null};
    const timestamp=d=>Date.parse(d+'T00:00:00Z'),day=86400000,through=Math.min(timestamp(end),timestamp(today)),start=timestamp(s.received);
    const calendar=Math.max(0,Math.round((through-start)/day)+1),paused=s.pauses.reduce((sum,p)=>sum+Math.max(0,Math.round((Math.min(p.end?timestamp(p.end):through+day,through+day)-Math.max(timestamp(p.start),start))/day)),0);
    return {calendar,paused,active:Math.max(0,calendar-paused),end};
  }
  function productionPage() {
    const s=S(),c=counts(),unknown=s.source&&!s.source.pausesComplete;
    return `<div class="lse-stack">${section('Производство и календарный учёт',`<dl class="lse-facts"><div><dt>Календарные дни</dt><dd>${c.calendar}</dd></div><div><dt>Дни приостановок</dt><dd>${unknown?'Неизвестно':c.paused}</dd></div><div><dt>Дни без приостановок</dt><dd>${unknown?'Неизвестно':c.active}</dd></div><div><dt>Учтено по</dt><dd>${date(c.end)}</dd></div><div><dt>Действующий срок</dt><dd>${date(s.deadline)}</dd></div><div><dt>Последний запрошенный срок</dt><dd>${date(s.deadlineEvents.filter(e=>e.type==='Запрошенное продление').at(-1)?.due)}</dd></div><div><dt>Исходный срок</dt><dd>${date(s.deadlineEvents.filter(e=>e.type==='Исходный срок').at(-1)?.due||s.deadline)}</dd></div><div><dt>Согласованный срок</dt><dd>${date(s.deadlineEvents.filter(e=>e.type==='Согласованный срок').at(-1)?.due)}</dd></div><div><dt>Календарные дни после срока</dt><dd>${s.deadline&&!['completed','without_execution'].includes(s.status)?Math.max(0,Math.round((Date.parse(today)-Date.parse(s.deadline))/86400000)):'Неизвестно'}</dd></div></dl><div class="lse-work-actions">${button('pause','Приостановить')}${button('resume','Возобновить')}${button('deadline','Редактировать срок')}</div>${help('Календарные дни считаются отдельно от юридической оценки нарушения срока. Неизвестная полнота старых приостановок не заменяется нулём.')}`,'','production')}${disclosure('Приостановки и события сроков',table(['Событие','Дата / интервал','Основание'],[...s.pauses.map(p=>['Приостановка',`${date(p.start)} → ${p.end?date(p.end):'действует'}`,h(p.reason)]),...s.deadlineEvents.map(e=>[h(e.type),`${date(e.date)} → ${date(e.due)}`,h(e.reason)])]),`${s.pauses.length+s.deadlineEvents.length} событий`)}${section('Длительность и подтверждения срока',`<dl class="lse-facts"><div><dt>Полнота причин</dt><dd>${s.timing.complete?'Подтверждена':'Не подтверждена'}</dd></div><div><dt>Основная причина</dt><dd>${h(delays[s.timing.primary]||'Не указана')}</dd></div></dl>${s.timing.reasons.map(r=>`<p class="lse-contact-line">${h(delays[r.reason])}<br><span class="lse-small lse-muted">${h(r.comment)}</span> ${detailDoc(r.document)}</p>`).join('')}${table(['Факт','Значение','Подтверждение'],[['Информирование о сроке',yesNo[s.timing.notification_sent],detailDoc(s.timing.notification_document)],['Ходатайство о продлении',yesNo[s.timing.extension_requested],detailDoc(s.timing.request_document)],['Нарушение срока',yesNo[s.timing.deadline_breached],detailDoc(s.timing.breach_document)]])}`,button('timing','Редактировать'),'timing')}</div>`;
  }
  function timingRow(x={key:uid('delay'),reason:'',comment:'',document:''}) {return `<div class="lse-repeat-row" data-delay-row="${h(x.key)}"><div class="lse-fields">${select(`delay_reason_${x.key}`,'Причина длительности',{'':'Выберите причину',...delays},x.reason)}${field(`delay_comment_${x.key}`,'Пояснение',x.comment)}</div>${docSlot(`delay_document_${x.key}`,'Подтверждение причины',x.document)}${button('remove_row','Убрать причину',{text:true})}</div>`;}
  function timingForm() {const t=S().timing;extendedForm('timing','Редактировать длительность и подтверждения',`<div id="delay-rows">${t.reasons.map(x=>timingRow(x)).join('')}</div>${button('add_delay','Добавить причину')}${select('primary','Основная причина',{'':'Не указана',...Object.fromEntries(t.reasons.map(r=>[r.reason,delays[r.reason]]))},t.primary)}${checkbox('complete','Список причин заполнен полностью',t.complete)}${['notification','request','breach'].map((slot,i)=>{const flag=['notification_sent','extension_requested','deadline_breached'][i];return disclosure(['Информирование о невозможности исполнить в срок','Направление ходатайства о продлении','Оценка нарушения срока'][i],`${select(flag,'Подтверждённый факт',yesNo,t[flag])}${slot!=='breach'?field(slot==='notification'?'notification_on':'request_on','Фактическая дата',t[slot==='notification'?'notification_on':'request_on'],'date'):area('breach_basis','Основание оценки срока',t.breach_basis)}${docSlot(slot+'_document','Документ подтверждения',t[slot+'_document'])}`);}).join('')}${reasonField()}`);}
  function previousRow(x={key:uid('prev'),reference:'',organization:'',group:'',same:'',confirms:'',document:''}) {return `<div class="lse-repeat-row" data-previous-row="${x.key}"><div class="lse-fields">${field('previous_reference_'+x.key,'Номер / реквизиты заключения',x.reference)}${field('previous_organization_'+x.key,'Учреждение / эксперт',x.organization)}${select('previous_group_'+x.key,'Группа учреждения',{'':'Неизвестно',ministry:'СЭУ Минюста России',other_state:'Иное государственное СЭУ',other:'Иное учреждение / частный эксперт'},x.group)}${select('previous_same_'+x.key,'Те же исходные данные',yesNo,x.same)}${select('previous_confirms_'+x.key,'Подтверждает прежние выводы',yesNo,x.confirms)}</div>${docSlot('previous_document_'+x.key,'Предыдущее заключение',x.document,['expert_conclusion'])}${button('remove_row','Убрать заключение',{text:true})}</div>`;}
  function classificationForm(){const s=S();extendedForm('classification','Редактировать характер экспертизы',`${select('classification','Характер назначения',{primary:'Первичная',additional:'Дополнительная',repeated:'Повторная'},s.classification)}${checkbox('commission','Комиссионная · один номер',s.commission)}<div id="previous-rows">${s.previous.map(previousRow).join('')}</div>${button('add_previous','Добавить предыдущее заключение')}${checkbox('previous_complete','Перечень предыдущих заключений полный',s.previousComplete)}${reasonField()}`);}
  function casePage(){const s=S();return core.casePage()+disclosure('Тип органа и признаки для отчёта',`<dl class="lse-facts"><div><dt>Тип органа</dt><dd>${h(authorities[s.case.authority_type])}</dd></div>${['16.1','16.2'].includes(s.specialty)?`<div><dt>Самовольное строение · 3214-р</dt><dd>${s.case.decree?'Да':'Не отмечено'}</dd></div><div><dt>Основание</dt><dd>${h(s.case.decree_basis||'Не указано')} ${detailDoc(s.case.decree_document)}</dd></div>`:''}</dl>`,s.case.decree?'3214-р':'','case-flags')+disclosure('Предыдущие заключения',table(['Реквизиты','Учреждение','Исходные данные','Выводы'],s.previous.map(p=>[h(p.reference),h(p.organization),yesNo[p.same],yesNo[p.confirms]]))+button('classification','Редактировать'),`${s.previous.length} заключений`,'previous')+section('Комплексная группа',`<p class="lse-small">${s.complex?h(s.groupTitle||'Общие материалы · отдельный номер по специальности'):'Работа не входит в комплексную группу'}</p>${s.groupWorks.map(w=>`<p class="lse-contact-line">${h(w.number)} · ${h(w.spec)} · ${w.closed?'Завершена':'В производстве'}</p>`).join('')}`,button('complex','Редактировать'),'complex');}
  function caseForm(){const c=S().case;extendedForm('editcase','Редактировать сведения дела',`<div class="lse-fields">${select('authority_type','Тип назначившего органа',authorities,c.authority_type)}${field('authority','Назначивший орган / заявитель',c.authority)}${field('official','Должностное лицо',c.official)}${field('contact','Контакты',c.contact)}${field('case_number','Номер дела / материала',c.case_number)}${area('description','Сведения о деле',c.description)}${area('basis_text','Реквизиты основания',c.basis_text)}${area('inventory','Опись материалов',c.inventory)}${area('questions_text','Поставленные вопросы',c.questions_text)}</div>${docSlot('basis_document','Постановление / определение',S().basisId,['basis'])}${['16.1','16.2'].includes(S().specialty)?`${checkbox('decree','Самовольное строение · 3214-р',c.decree,'Признак используется только для специальностей 16.1 и 16.2. Дополнительный документ необязателен.')}${area('decree_basis','Пояснение к 3214-р (необязательно)',c.decree_basis)}${docSlot('decree_document','Основание 3214-р (необязательно)',c.decree_document)}`:''}${reasonField()}`);}
  function allocationRow(x={key:uid('allocation'),reason:'',count:'',comment:'',document:''}) {return `<div class="lse-repeat-row" data-allocation-row="${h(x.key)}"><div class="lse-fields">${select('allocation_reason_'+x.key,'Причина нерешённых вопросов',{'':'Выберите причину',...unresolved},x.reason)}${field('allocation_count_'+x.key,'Количество вопросов',x.count,'number','min="1" step="1"')}${area('allocation_comment_'+x.key,'Пояснение',x.comment)}</div>${docSlot('allocation_document_'+x.key,'Подтверждение причины (необязательно)',x.document)}${button('remove_row','Убрать причину',{text:true})}</div>`;}
  function collectRows(form,attribute,fields) {return [...form.querySelectorAll('['+attribute+']')].map(row=>{const key=row.getAttribute(attribute);return {key,...Object.fromEntries(fields.map(([keyName,prefix])=>[keyName,form.elements.namedItem(prefix+key)?.value||'']))};});}
  function collectAllocations(form){return collectRows(form,'data-allocation-row',[['reason','allocation_reason_'],['count','allocation_count_'],['comment','allocation_comment_'],['document','allocation_document_']]);}
  function validateAllocations(items,total,complete) {
    if(items.some(x=>!x.reason||!Number.isInteger(Number(x.count))||Number(x.count)<1))return 'У каждой причины нужны название и положительное целое количество вопросов.';
    if(new Set(items.map(x=>x.reason)).size!==items.length)return 'Одна причина указана несколько раз. Объедините количество.';
    if(items.some(x=>x.reason==='other'&&!x.comment.trim()))return 'Поясните иную причину нерешённых вопросов.';
    const sum=items.reduce((n,x)=>n+Number(x.count),0);
    if(total!==''&&sum>Number(total))return 'Распределение причин превышает число нерешённых вопросов T.';
    if(complete&&(total===''||sum!==Number(total)))return 'Для отметки полного распределения сумма причин должна равняться T.';
    return '';
  }
  function sourceBanner(){const s=S();return `<div class="lse-readonly" data-feature="history-source"><strong>Историческая регистрация</strong> · ${h(s.source.historical_number)}<div class="lse-picker-tools">${button('source_snapshot','Исходные сведения',{text:true})}${button('historical','Редактировать отчётные сведения')}${!s.source.operational?button('activate','Подтвердить для нового учёта',{primary:true}):'<span class="lse-status">Новый учёт подтверждён</span>'}${help('Номера и фактический отдел сохраняются. Исполнители источника и назначения в АИС — разные сведения. Уточнение старого результата не завершает работу повторно.')}</div></div>`;}
  function sourceSnapshot(){const x=S().source.snapshot||S().source;a.showDialog('source_snapshot','Исходные сведения · только чтение',`<dl class="lse-facts">${[['Номер регистрации',x.number],['Прежний номер',x.historical_number],['Фактический отдел',x.department],['Поступление',date(x.received)],['Окончание в источнике',date(x.completed)],['Выдача в источнике',date(x.issued)],['Исполнитель в источнике',x.executor],['Специальность',x.raw?.specialty||'Неизвестно'],['Категория',x.raw?.category||'Неизвестно'],['Q / R / S / T',x.result?[x.result.q,x.result.r,x.result.s,x.result.t].map(v=>v===''?'?':v).join(' / '):'Неизвестно'],['Сложность',x.result?.complexity||'Неизвестно'],['Сумма в источнике',x.raw?.amount??'Неизвестно'],['Опись',x.raw?.case.inventory||'Не указана'],['Вопросы',x.raw?.case.questions_text||'Не указаны'],['Строка / снимок',`${x.row} / ${x.observed}`]].map(([k,v])=>`<div><dt>${h(k)}</dt><dd>${h(v)}</dd></div>`).join('')}</dl><p class="lse-inline-note">Условный сохранённый снимок. Google-таблица не запрашивается и не изменяется.</p>`);}
  function reportFields(d) {return `<div class="lse-fields">${select('kind','Вид результата',S().category==='6'?{research_act:a.kinds.research_act}:{expert_conclusion:a.kinds.expert_conclusion,sndz:'СНДЗ'},d.kind)}${field('completed_on','Дата окончания, если известна',d.completed_on,'date')}${field('complexity','Сложность',d.complexity,'number','min="1" step="1"')}${field('q','Q — поставленные вопросы',d.q,'number','min="0" step="1"')}${field('r','R — категорические ответы',d.r,'number','min="0" step="1"')}${field('s','S — вероятные ответы',d.s,'number','min="0" step="1"')}${field('t','T — нерешённые вопросы',d.t,'number','min="0" step="1"')}</div>${checkbox('statistics_complete','Статистика Q = R + S + T заполнена полностью',d.statistics_complete)}${select('sndz_reason','Причина полного СНДЗ (если результат СНДЗ)',{'':'Не определена',knowledge:'За пределами специальных знаний',materials:'Материалы непригодны / недостаточны',science:'Уровень науки и техники'},d.sndz_reason)}${area('sndz_comment','Пояснение СНДЗ',d.sndz_comment)}<div id="history-allocations">${(d.allocations||[]).map(allocationRow).join('')}</div>${button('history_add_allocation','Добавить причину нерешённых вопросов')}${checkbox('allocations_complete','Распределение T заполнено полностью',d.allocations_complete)}${area('note','Отчётное примечание',d.note)}`;}
  function historyForm(activate=false) {
    const s=S(),d=s.source.result||a.emptyResult(),closed=['completed','without_execution'].includes(s.status);
    extendedForm(activate?'activate':'historical',activate?'Подтвердить старую работу для нового учёта':'Редактировать исторические отчётные сведения',`${activate?`<div class="lse-fields">${select('classification','Характер назначения',{primary:'Первичная',repeated:'Повторная',additional:'Дополнительная'},s.classification)}${select('commission','Состав',{no:'Единоличная',yes:'Комиссионная'},s.commission?'yes':'no')}${select('specialty','Специальность',specs,s.specialty)}</div>${checkbox('complex_confirm','Состав комплексной группы проверен',false)}${docSlot('history_basis','Документ-основание',s.basisId,['basis'])}${checkbox('pauses_complete','История приостановок полная',s.source.pausesComplete)}<div id="historical-pauses">${s.pauses.filter(x=>x.end).map(x=>pauseRow(x)).join('')}</div>${button('add_historical_pause','Добавить подтверждённый интервал')}${s.status==='suspended'?field('open_pause','Начало открытой приостановки',s.pause?.date||'','date'):''}`:select('specialty','Специальность',specs,s.specialty)}${closed?s.status==='without_execution'?`${field('returned_on','Дата решения, если известна',s.source.completed,'date')}${select('return_reason','Причина возврата',{'':'Неизвестна',...returns},s.returnReason||'')}${area('return_comment','Пояснение',s.returnComment||'')}`:reportFields(d):'<p class="lse-inline-note">Для работы в производстве результат не подставляется.</p>'}${activate&&closed?docSlot('history_result','Подтверждённый итоговый документ','',s.status==='without_execution'?['return_decision']:['expert_conclusion','sndz','research_act']):''}${reasonField()}`,{},activate?'Подтвердить для нового учёта':'Сохранить уточнение');
  }
  function pauseRow(x={start:'',end:'',reason:''}) {const key=uid('pause');return `<div class="lse-repeat-row" data-pause-row="${key}"><div class="lse-fields">${field('historical_start_'+key,'Приостановлена',x.start,'date')}${field('historical_end_'+key,'Возобновлена',x.end,'date')}${field('historical_reason_'+key,'Основание интервала',x.reason)}</div>${button('remove_row','Убрать интервал',{text:true})}</div>`;}
  function historyPage(){const s=S();return `${s.source?sourceBanner():''}${s.source?disclosure('Исходный снимок',`<p class="lse-small">${h(s.source.number)} · прежний ${h(s.source.historical_number)} · отдел ${h(s.source.department)}</p>${button('source_snapshot','Показать исходные сведения',{text:true})}`,'Только чтение'):''}${s.corrections.length?disclosure('История уточнений',table(['Событие','Изменения'],s.corrections.map(c=>[h(c.title),h(c.description)])),`${s.corrections.length}`):''}${s.resultRevisions.length?disclosure('Редакции результата',table(['Редакция','Вид / дата','Документ'],s.resultRevisions.map((r,i)=>[String(i+1),`${h(a.kinds[r.kind])} · ${date(r.completed_on)}`,detailDoc(r.documentId)])),`${s.resultRevisions.length}`):''}${core.historyPage()}`;}
  function openUpload(options={}) {
    core.openUpload(options);
    const m=M(),form=$('#upload-form');m.expanded=true;m.options=options;
    if(!options.existingId){form.insertAdjacentHTML('afterbegin',`<div class="lse-fields">${select('source','Источник документа',{copy:'Файл / фото с компьютера',paper:'Бумажный оригинал',link:'Внешняя ссылка',folder:'Файлы из выбранной папки'},'copy')}${field('source_url','Адрес документа / ссылка','')}</div><p class="lse-inline-note" id="source-note">В макете выбранные файлы остаются только в памяти вкладки.</p>`);form.elements.namedItem('source_url').closest('label').hidden=true;}
    const file=$('#upload-file');file.multiple=!options.existingId&&!options.selectResult;
    if(!options.existingId&&!options.selectResult)$('#upload-file-caption').insertAdjacentHTML('afterend',button('sample_folder','Использовать пример папки',{text:true}));
    if(!options.existingId){$('#upload-form .lse-form-footer').insertAdjacentHTML('beforebegin',`${area('archive_note','Примечание к связи с экспертизой')}<div id="batch-file-rows"></div>`);}
    M().initial=JSON.stringify(values(form));
  }
  function batchFileRows(files){const box=$('#batch-file-rows');if(!box)return;box.innerHTML=files.length>1?disclosure('Параметры каждого файла',files.map((file,i)=>`<div class="lse-repeat-row"><p class="lse-small">${h(file.webkitRelativePath||file.relativePath||file.name)}</p><div class="lse-fields">${field('file_title_'+i,'Название документа',file.name)}${select('file_kind_'+i,'Вид документа',a.kinds,$('#upload-form [name="kind"]').value)}</div></div>`).join(''),files.length+' файлов'):'';initializeSelects(box);}
  function sourceChanged(){const form=$('#upload-form'),source=form.elements.namedItem('source')?.value||'copy',file=$('#upload-file');file.required=['copy','folder'].includes(source);file.closest('label').hidden=!file.required;form.elements.namedItem('source_url').closest('label').hidden=source!=='link';if(source==='folder')file.setAttribute('webkitdirectory','');else file.removeAttribute('webkitdirectory');$('#source-note').textContent=source==='folder'?'Разовый выбор папки пользователем. Серверный каталог настраивает администратор отдельно.':source==='link'?'Адрес только сохраняется в локальном макете. Внешний файл здесь не запрашивается.':source==='paper'?'Регистрируется оригинал без электронного файла; скан можно добавить позднее.':'Выбранный файл остаётся в этой вкладке.';}
  async function submitUpload(form) {
    if(a.uploading)return;const refusal=denied('upload');if(refusal){a.toast(refusal);return;}
    const m=M(),v=values(form),source=v.source||'copy',files=m.files||(m.file?[m.file]:[...$('#upload-file').files]);
    if(['copy','folder'].includes(source)&&!files.length)return uploadError('Выберите файл или используйте тестовый пример.');
    if(files.length>100)return uploadError('В одной выборке допустимо до 100 файлов.');
    if(docContext?.allowed&&!docContext.allowed.includes(v.kind||m.kind))return uploadError('Для этого поля нужен другой вид документа. Измените вид или выберите подходящий файл.');
    if(source==='link'&&!String(v.source_url||'').trim())return uploadError('Укажите адрес документа.');
    if(['paper','link'].includes(source)&&!String(v.title||'').trim())return uploadError('Укажите название документа.');
    a.uploading=true;$('#upload-progress').hidden=false;$('#upload-error').hidden=true;for(const e of form.elements)e.disabled=true;
    await new Promise(resolve=>setTimeout(resolve,300));
    if($('#upload-simulate-error').checked&&!m.failed){m.failed=true;a.uploading=false;for(const e of form.elements)e.disabled=false;$('#upload-progress').hidden=true;$('#upload-submit').textContent='Повторить';uploadError('Тестовая ошибка: выбранные файлы сохранены. Повтор добавит только отсутствующие документы.');return;}
    const before=S().docs.length,created=[];
    for(const [fileIndex,file] of (['copy','folder'].includes(source)?files:[null]).entries()){
      let d=a.currentDoc(m.existingId);
      if(!d){d={id:uid('doc'),kind:v['file_kind_'+fileIndex]||v.kind||m.kind,title:String(v['file_title_'+fileIndex]||v.title||'').trim()||(file?.name||'Документ'),note:v.archive_note||'',source:source==='folder'?'copy':source,source_url:source==='link'?v.source_url:'',versions:[]};if(files.length>1&&file&&!v['file_title_'+fileIndex])d.title=file.name;S().docs.push(d);}
      if(file){const version={id:uid('v'),name:file.name,type:file.type,demo:!!file.demo};if(!file.demo){version.url=URL.createObjectURL(file);a.urls.add(version.url);}d.versions.push(version);d.source='copy';if(file.webkitRelativePath||file.relativePath)d.relativePath=file.webkitRelativePath||file.relativePath;}
      created.push(d);
    }
    const doc=created[0];S().checked=false;S().version++;
    if(m.selectResult){if(U().editing)U().draft.documentId=doc.id;else if(S().result)S().result.documentId=doc.id;}
    a.event(m.existingId?'Добавлена версия документа':`Добавлено документов: ${S().docs.length-before}`,created.map(d=>d.title).join(', '));a.uploading=false;
    if(docContext)setSlot(doc.id);else if(viewReturn){const snapshot=viewReturn;viewReturn=null;restoreSnapshot(snapshot);}else {core.closeDialog();render();}
    a.toast(m.existingId?'Новая версия добавлена к тому же документу':'Документы добавлены в макет');
  }
  function uploadError(message){$('#upload-error').hidden=false;$('#upload-error').textContent=message;}
  function documentsPage(){return core.documentsPage().replace('<div id="doc-list">',`<div class="lse-picker-tools">${button('folder_upload','Загрузить папку')}${button('source_document','Добавить ссылку / оригинал')}${help('Файлы или папка выбираются явно. Здесь не происходит подключения к сетевому ресурсу. В рабочей АИС путь сервера настраивает администратор.')}</div><div id="doc-list">`);}
  let viewReturn=null;
  function viewDocument(id,index){const d=a.currentDoc(id);if(!d)return;if($('#lse-dialog').open&&!['view','link_view'].includes(M()?.type)&&!viewReturn)viewReturn=formSnapshot();if(d.source==='link'&&!d.versions.length)a.showDialog('link_view',d.title,`<p class="lse-small">Источник: внешняя ссылка</p><p class="lse-preserve lse-contact-line">${h(d.source_url)}</p><p class="lse-inline-note">В рабочей версии файл открывается через доступный источник. В макете внешние ресурсы не загружаются.</p>`);else {core.viewDocument(id,index);if(d.relativePath)$('#lse-dialog .lse-dialog-body').insertAdjacentHTML('afterbegin',`<p class="lse-inline-note">Путь выбранного файла: ${h(d.relativePath)}</p>`);}}
  function closeDialog(){if(a.uploading)return;if(docContext){const ctx=docContext;docContext=null;restoreSnapshot(ctx.snapshot);return;}if(viewReturn){const saved=viewReturn;viewReturn=null;restoreSnapshot(saved);return;}core.closeDialog();}
  function letterStatus(l){return l.sent?'Отправлено':l.received?'Получено':l.registration?'Зарегистрировано':'Черновик';}
  function lettersPage(){const s=S();return section('Переписка по экспертизе',table(['Дата','Направление / состояние','Номер / тема','Контроль',''],s.letters.map(l=>[date(l.date),`${h(l.direction)}<small>${letterStatus(l)}</small>`,`${h(l.registration?.number||l.number||'Без номера')}<br>${h(l.subject)}${l.parentId?'<small>Ответ на связанное письмо</small>':''}`,l.control?`${l.control.status==='open'?'На контроле':'Контроль закрыт'}<small>${h(l.control.responsible||'Не назначен')} · ${date(l.control.due)}</small>`:'Не поставлено',button('view_letter','Открыть',{id:l.id,text:true})])),button('letter','Добавить письмо',{primary:true}),'correspondence');}
  function recipientRow(x={name:'',address:'',email:''}) {const key=uid('recipient');return `<div class="lse-repeat-row" data-recipient-row="${key}"><div class="lse-fields">${field('recipient_name_'+key,'Наименование адресата',x.name)}${field('recipient_address_'+key,'Адрес',x.address)}${field('recipient_email_'+key,'Email',x.email,'email')}</div>${button('remove_row','Убрать адресата',{text:true})}</div>`;}
  function letterForm(letter=null,parent=null) {
    const d=letter||{directionCode:parent?(parent.directionCode==='incoming'?'outgoing':'incoming'):'incoming',kind:'',date:today,number:'',subject:parent?'Ответ: '+parent.subject:'',body:'',sender:'',external_on:'',received_on:'',recipients:parent?.directionCode==='incoming'?[{name:parent.sender||parent.recipient||'Назначивший орган',address:'',email:''}]:[],attachments:[],note:'',replyCompleteness:''};
    extendedForm('letter_edit',letter?'Редактировать письмо':parent?'Добавить ответ':'Добавить письмо',`<div class="lse-fields">${letter||parent?`<input type="hidden" name="direction" value="${h(d.directionCode)}"><p class="lse-small">${d.directionCode==='incoming'?'Входящее':'Исходящее'}</p>`:select('direction','Направление',{incoming:'Входящее',outgoing:'Исходящее'},d.directionCode)}${select('kind','Вид письма',{'':'Не определён',...S().letterKinds},d.kind)}${select('department','Отдел',{'':'Не указан','1':'1 · исторический','3':'3','4':'4'},S().department)}${field('date','Дата документа',d.date,'date')}${field('subject','Тема',d.subject,'text','required')}${field('sender','Отправитель',d.sender)}${field('number','Внешний номер',d.number)}${field('external_on','Дата внешнего письма',d.external_on,'date')}${field('received_on','Дата поступления',d.received_on,'date')}${area('body','Содержание',d.body)}${area('note','Примечание',d.note)}</div><div id="letter-recipients">${d.recipients.map(recipientRow).join('')}</div>${button('add_recipient','Добавить адресата')}${parent||d.parentId?select('replyCompleteness','Полнота ответа',{'':'Не определена',partial:'Частичный',complete:'Полный'},d.replyCompleteness):''}<div id="letter-attachments">${(d.attachments.length?d.attachments:['']).map((id,index)=>`<div class="lse-repeat-row">${docSlot('letter_document_'+index,'Приложение к письму',id)}${button('remove_row','Убрать приложение',{text:true})}</div>`).join('')}</div>${button('add_letter_attachment','Добавить приложение')}${reasonField()}`,{letterId:letter?.id,parentId:parent?.id||d.parentId||null},'Сохранить черновик');
  }
  function viewLetter(id) {const l=S().letters.find(x=>x.id===id);if(!l)return;
    a.showDialog('letterview',l.subject,`<div data-feature="letter-lifecycle"><div class="lse-picker-tools"><span class="lse-status">${letterStatus(l)}</span>${button('letter_edit','Редактировать',{id,reason:l.registration?'Зарегистрированное содержание заморожено. Используйте отдельные действия.':''})}${button('letter_attachment','Добавить приложение',{id})}${button('letter_reply','Добавить ответ',{id})}${button('letter_register','Зарегистрировать',{id,reason:l.registration?'Письмо уже зарегистрировано.':''})}${l.directionCode==='incoming'?button('letter_receive','Подтвердить получение',{id,reason:l.received?'Получение уже подтверждено.':''}):button('letter_send','Записать отправку',{id,reason:!l.registration?'Сначала зарегистрируйте письмо.':''})}${button('letter_deliver','Подтвердить доставку',{id,reason:!l.sent?'Сначала запишите фактическую отправку.':''})}</div><dl class="lse-facts">${[['Направление',l.direction],['Регистрационный номер',l.registration?.number||'Не зарегистрировано'],['Внешний номер',l.number||'Не указан'],['Отправитель',l.sender||'Не указан'],['Адресаты',l.recipients.map(x=>x.name).join(', ')||'Не указаны'],['Ответ на',l.parentId?S().letters.find(x=>x.id===l.parentId)?.subject||'Связанное письмо':'—']].map(([k,v])=>`<div><dt>${h(k)}</dt><dd>${h(v)}</dd></div>`).join('')}</dl><p class="lse-preserve lse-contact-line">${h(l.body)}</p>${l.attachments.map(detailDoc).join('')}${disclosure('Контроль и сроки',`<p class="lse-small">${l.control?`${l.control.status==='open'?'Открыт':'Закрыт'} · ${h(l.control.responsible||'Без ответственного')} · срок ${date(l.control.due)}`:'На контроль не поставлено'}</p><div class="lse-picker-tools">${button('letter_assign','Назначить ответственного',{id})}${button('letter_control','Поставить на контроль',{id,reason:l.control?'Контроль уже создан.':''})}${button('letter_deadline','Редактировать срок',{id,reason:!l.control?'Сначала поставьте письмо на контроль.':''})}${button('letter_close','Закрыть контроль',{id,reason:l.control?.status!=='open'?'Нет открытого контроля.':''})}${button('letter_reopen','Возобновить контроль',{id,reason:l.control?.status!=='closed'?'Нет закрытого контроля.':''})}</div>`)}${disclosure('Отправки и ответы',table(['Событие','Дата','Подробности'],[...(l.dispatches||[]).map(d=>['Отправка',date(d.date),`${h(d.channel)} · ${h(d.tracking)}`]),...(l.deliveries||[]).map(d=>['Доставка',date(d.date),h(d.recipient)]),...S().letters.filter(x=>x.parentId===id).map(x=>['Ответ',date(x.date),h(x.subject)])]))}<p class="lse-inline-note">Здесь фиксируется факт; макет не отправляет письма и не выполняет доставку.</p></div>`,{letter:l,letterId:id},true);
  }
  function letterAction(action,id) {const l=S().letters.find(x=>x.id===id);if(!l)return;
    const headings={letter_register:'Зарегистрировать письмо',letter_send:'Записать фактическую отправку',letter_receive:'Подтвердить получение',letter_deliver:'Подтвердить доставку',letter_assign:'Назначить ответственного',letter_control:'Поставить на контроль',letter_deadline:'Редактировать срок контроля',letter_close:'Закрыть контроль',letter_reopen:'Возобновить контроль'};
    let body='';
    if(['letter_register','letter_send','letter_receive','letter_deliver'].includes(action))body+=field('date','Фактическая дата',today,'date','required');
    if(action==='letter_register')body+=select('journal','Журнал',{incoming:'Входящие',outgoing:'Исходящие'},l.directionCode)+field('registration_number','Внутренний регистрационный номер','','text','required');
    if(action==='letter_send')body+=select('channel','Способ отправки',{post:'Почта',email:'Электронная почта',courier:'Курьер',personal:'Лично'},'post')+`<fieldset><legend>Адресаты этой отправки</legend>${l.recipients.map((x,i)=>checkbox('recipients',x.name,true).replace('type="checkbox"',`type="checkbox" value="${i}"`)).join('')}</fieldset>`+field('tracking','Трек / идентификатор');
    if(action==='letter_deliver')body+=select('dispatch','Отправка',Object.fromEntries((l.dispatches||[]).map((x,i)=>[String(i),date(x.date)+' · '+x.channel])),'0')+field('recipient','Получивший адресат',l.recipients[0]?.name||'');
    if(['letter_assign','letter_control'].includes(action))body+=select('responsible','Ответственный',{'':'Не назначен','Лалетина О.В.':'Лалетина О.В.','Делопроизводитель (пример)':'Делопроизводитель (пример)'},l.control?.responsible||'');
    if(['letter_control','letter_deadline'].includes(action))body+=field('due','Срок, если известен',l.control?.due||'','date')+area('due_basis','Основание срока',l.control?.basis||'');
    if(action==='letter_close')body+=select('closure_reason','Основание закрытия',{reply_sent:'Направлен ответ',reply_received:'Получен ответ',other:'Иное основание'},'reply_sent')+select('reply','Завершающий ответ',{'':'Не выбран',...Object.fromEntries(S().letters.filter(x=>x.parentId===id).map(x=>[x.id,x.subject]))},'')+area('comment','Комментарий');
    if(['letter_send','letter_receive','letter_deliver'].includes(action))body+=docSlot('evidence','Подтверждение факта (необязательно)');
    if(action==='letter_reopen')body+=area('comment','Комментарий');
    extendedForm(action,headings[action],body+reasonField(),{letterId:id,letter:l},'Сохранить факт');
  }
  function packageWorks(){const s=S();return [{number:s.number,spec:s.specialty,closed:['completed','without_execution'].includes(s.status)},...s.groupWorks];}
  function packageWarnings(){const s=S(),warnings=[];for(const w of packageWorks()){
    const items=s.packageItems.filter(x=>x.work===w.number);
    let required=w.number===s.number?a.requiredDocs():['subscription','cover'];
    if(s.billing[w.number]===true&&!required.includes('invoice'))required.push('invoice');
    for(const kind of required){if(w.number===s.number&&kind===s.result?.kind&&a.currentDoc(s.result.documentId))continue;if(!items.some(x=>x.kind===kind&&a.currentDoc(x.document)))warnings.push(w.number+' · '+a.kinds[kind]);}
    if(s.commission&&w.number===s.number){const distinct=new Set(items.filter(x=>x.kind==='subscription').map(x=>x.document));if(distinct.size<s.employees.length)warnings.push('Подписки на каждого участника комиссии: '+distinct.size+' из '+s.employees.length);}
    }return warnings;
  }
  function issuancePage(){const s=S();if(s.issued)return core.issuancePage()+disclosure('Комплект и подтверждение выдачи',`${h(s.packageNote||'Примечания к комплекту не добавлены')}<div>${detailDoc(s.issued.evidence)}</div>${table(['Работа','Документ','Роль'],s.packageItems.map(x=>[h(x.work),detailDoc(x.document),h(a.kinds[x.kind])]))}`,`${s.packageItems.length} приложений`,'issue-proof');
    const warnings=packageWarnings();return `<div class="lse-work-grid">${section('Подготовка выдачи',`<div class="lse-form"><label class="lse-field"><span>Возвращаемые материалы</span><textarea id="issue-materials" rows="3"${!a.rights[U().profile].includes('issue_prepare')?' disabled':''}>${h(s.materials)}</textarea></label><div class="lse-fields">${packageWorks().map(w=>select('billing_'+w.number,w.number+' · платность',{'':'Не уточнена',false:'Не платная',true:'Платная — нужен счёт'},s.billing[w.number]===undefined?'':String(s.billing[w.number]),!permitted('package_edit')?'disabled':'')).join('')}</div><div class="lse-form-footer">${button('prepare','Сохранить состав')}${button('package_edit','Редактировать комплект')}${button('check','Проверить комплект')}${button('issue','Выдать материалы',{primary:true})}</div>${s.checked?`<div class="lse-inline-success">Комплект проверен. Напоминаний: ${warnings.length}.</div>`:''}<div class="lse-helper-line">${help('Отсутствие файлов — напоминания. Для выдачи нужны завершённые работы, описанные материалы, известная платность и актуальная проверка. Счёт не подтверждает оплату.')}</div></div>`,'','issuance')}<div>${section('Документы по работам',`${table(['Работа','Роль','Документ',''],s.packageItems.map(x=>[h(x.work),h(a.kinds[x.kind]),detailDoc(x.document),button('edit_package_item','Редактировать',{id:x.id,text:true})+button('remove_package_item','Убрать из комплекта',{id:x.id,text:true})]))}<div class="lse-work-actions">${button('attach_issue','Добавить документ по работе')}</div>`,'','package-documents')}${disclosure('Что ещё не приложено',`<ul class="lse-checklist">${warnings.map(x=>`<li><span class="lse-missingmark">○</span>${h(x)}</li>`).join('')}</ul>`,String(warnings.length))}</div></div>`;
  }
  function itemForm(item=null){extendedForm('attach_issue',item?'Редактировать приложение':'Добавить документ в комплект',`${select('work','Работа',Object.fromEntries(packageWorks().map(x=>[x.number,x.number])),item?.work||S().number)}${select('kind','Роль документа',{subscription:'Подписка эксперта',cover:'Сопроводительное',notification:'Уведомление',invoice:'Счёт',other:'Иное приложение'},item?.kind||'subscription')}${docSlot('document','Документ',item?.document||'',item?.kind&&item.kind!=='other'?[item.kind]:null)}${area('note','Примечание к приложению',item?.note||'')}${reasonField()}`,{itemId:item?.id});}
  function issueForm(){extendedForm('issue','Записать фактическую выдачу',`<div class="lse-fields">${field('date','Дата выдачи',today,'date','required')}${select('method','Способ',{personal:'Лично',post:'Почтой',courier:'Курьером'},'personal')}${field('recipient','Получатель','','text','required')}${field('basis','Основание получения','','text','required')}${field('tracking','Трек / идентификатор')}${area('comment','Комментарий')}</div>${docSlot('evidence','Подтверждение выдачи (необязательно)')}${reasonField()}`,{},'Подтвердить выдачу');}
  function render(){
    const selected=U().tab;if(selected==='production')U().tab='work';
    core.render();U().tab=selected;
    $('#lse-identity .lse-heading-actions').insertAdjacentHTML('beforeend',button('refresh_card','↻',{tip:'Обновить сведения карточки. В этом макете — локальная проверка, без запроса к серверу; введённые данные сохраняются.'}));
    if(selected==='production'){
      $('#lse-page').innerHTML=productionPage();$('#lse-page').setAttribute('aria-labelledby','tab-production');
      for(const tab of document.querySelectorAll('[data-tab]')){const active=tab.dataset.tab==='production';tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;}
    }
    if(U().editing&&selected!=='work')$('#lse-page').insertAdjacentHTML('afterbegin',`<div class="lse-editor-banner">Черновик результата сохранён в этой вкладке. ${button('return_result','Вернуться к редактированию',{text:true})}</div>`);
    // Explicit defaults also keep the standalone DOM test environment consistent.
    initializeSelects($('#lse-page'));
    if(S().source)$('#lse-identity').insertAdjacentHTML('beforeend',`<p class="lse-inline-note">Прежний номер: ${h(S().source.historical_number)} · фактический отдел ${h(S().source.department)}</p>`);
  }
  function initializeSelects(root){for(const el of root.querySelectorAll('select')){const initial=el.querySelector('option[selected]');if(initial)el.value=initial.value;}}
  function captureResult(){a.captureDraft();if(U().editing&&$('#result-form'))U().draft.allocations=collectAllocations($('#result-form'));}
  function route(tab){captureResult();core.route(tab);}
  function finish(message='Изменения сохранены в прототипе.'){S().version++;releaseAttempt();core.closeDialog();a.notice(message);}
  function reportValue(v,form){return {...a.emptyResult(v.kind),...Object.fromEntries(['kind','completed_on','complexity','q','r','s','t','sndz_reason','sndz_comment','note'].map(k=>[k,v[k]||''])),statistics_complete:new FormData(form).has('statistics_complete'),allocations_complete:new FormData(form).has('allocations_complete'),allocations:collectAllocations(form)};}
  function validateReport(d){
    if(d.completed_on&&(d.completed_on<S().received||d.completed_on>today))return 'Проверьте дату окончания: от поступления до текущего дня.';
    if(['q','r','s','t'].some(k=>d[k]!==''&&(!Number.isInteger(Number(d[k]))||Number(d[k])<0)))return 'Показатели Q/R/S/T — целые неотрицательные числа или пустое значение.';
    const sum=['r','s','t'].reduce((n,k)=>n+(d[k]===''?0:Number(d[k])),0);
    if(d.q!==''&&(sum>Number(d.q)||['r','s','t'].every(k=>d[k]!=='')&&sum!==Number(d.q)))return 'Проверьте Q = R + S + T.';
    if(d.statistics_complete&&['q','r','s','t'].some(k=>d[k]===''))return 'Для признака полноты заполните Q/R/S/T, включая известные нули.';
    return validateAllocations(d.allocations,d.t,d.allocations_complete);
  }
  function errorFor(form,message){let box=form.querySelector('[role="alert"]');if(!box){box=document.createElement('div');box.className='lse-inline-error';box.setAttribute('role','alert');form.append(box);}box.hidden=false;box.textContent=message;return box;}
  function releaseAttempt(){if(revisionAttempt){for(const [el,disabled] of revisionAttempt.controls||[])el.disabled=disabled;revisionAttempt=null;}for(const el of document.querySelectorAll('.lse-lab select,.lse-lab button'))el.disabled=false;}
  function guarded(form,run){
    if(revisionAttempt?.form===form){if(revisionAttempt.type==='conflict'&&!revisionAttempt.accepted)return;const attempt=revisionAttempt;releaseAttempt();attempt.run();return;}
    const mode=$('#lab-failure').value;if(mode==='none'){run();return;}
    $('#lab-failure').value='none';const box=errorFor(form,'');
    const messages={error:'Тестовая ошибка сохранения. Запись не изменена, поля сохранены. Можно исправить ввод и повторить.',uncertain:'Ответ не получен (тест). Исходный пакет сохранён. Повтор завершит ту же попытку без дублирования.',conflict:'Тестовый конфликт: появилась новая версия карточки. Введённые данные сохранены. Примите актуальную версию для новой попытки.',denied:'Тестовый отказ в праве: изменение не применено. Ввод сохранён. Повторная проверка моделирует восстановление разрешения.'};
    box.textContent=messages[mode];
    if(['uncertain','conflict'].includes(mode)){
      revisionAttempt={form,run,type:mode,accepted:false,controls:[]};
      if(mode==='conflict'){S().version++;box.insertAdjacentHTML('beforeend','<div>'+button('accept_version','Принять версию '+S().version)+'</div>');}
      else{for(const el of form.elements){revisionAttempt.controls.push([el,el.disabled]);el.disabled=true;}box.insertAdjacentHTML('beforeend','<div>'+button('retry_save','Повторить ту же попытку')+'</div>');for(const el of document.querySelectorAll('.lse-lab select,.lse-lab button'))el.disabled=true;}
    }
  }
  function submitResult(){const form=$('#result-form');captureResult();const err=validateAllocations(U().draft.allocations||[],U().draft.t,U().draft.allocations_complete);if(err){a.resultError(err);return;}guarded(form,()=>{const before=S().history.length;core.submitResult();if(S().history.length>before){S().resultRevisions.push(structuredClone(S().result));S().version++;}});}
  function submitModal(form){guarded(form,()=>saveModal(form));}
  function saveModal(form){
    const type=M()?.type,v=values(form),s=S(),fd=new FormData(form),refusal=denied(type);if(refusal){a.modalError(refusal);return;}
    const custom=['assign','reassign','editcase','classification','complex','timing','historical','activate','deadline','return','prepare','check','package_edit','attach_issue','issue','letter_edit'];
    if(!custom.includes(type)&&!type.startsWith('letter_')){const before=s.history.length;core.submitModal(form);if(s.history.length>before){s.version++;if(type==='pause')s.pauses.push({start:v.date,end:null,reason:v.reason});if(type==='resume'){const p=s.pauses.find(x=>!x.end);if(p)p.end=v.date;}if(type==='complete')s.closures.push({date:s.result.completed_on,kind:s.result.kind,reason:v.reason});}return;}
    if(!String(v.reason||'').trim()){a.modalError('Укажите основание изменения.');return;}
    if(v.date&&((!type.startsWith('letter_')&&v.date<s.received)||v.date>today)){a.modalError(type.startsWith('letter_')?'Фактическая дата не может быть в будущем.':'Дата события должна быть от поступления до текущего дня.');return;}
    if(['assign','reassign'].includes(type)){
      const next=fd.getAll('employees');if((s.commission&&next.length<2)||(!s.commission&&next.length!==1)){a.modalError(s.commission?'Для комиссии нужны минимум два эксперта.':'Для единоличной работы выберите одного эксперта.');return;}
      for(const old of s.assignments)if(!old.ended&&!next.includes(old.name))old.ended=today;
      for(const name of next)if(!s.assignments.some(x=>x.name===name&&!x.ended))s.assignments.push({id:uid('assignment'),name,started:today,ended:null,reason:v.reason});
      s.employees=next;a.event(type==='reassign'?'Работа перепоручена':'Состав исполнителей изменён',v.reason);
    } else if(type==='editcase'){
      for(const key of ['authority_type','authority','official','contact','case_number','description','basis_text','inventory','questions_text'])s.case[key]=v[key]||'';
      s.basisId=v.basis_document||s.basisId;if(['16.1','16.2'].includes(s.specialty)){s.case.decree=fd.has('decree');s.case.decree_basis=v.decree_basis||'';s.case.decree_document=v.decree_document||'';}a.event('Сведения дела изменены',v.reason);
    } else if(type==='classification'){
      const rows=collectRows(form,'data-previous-row',[['reference','previous_reference_'],['organization','previous_organization_'],['group','previous_group_'],['same','previous_same_'],['confirms','previous_confirms_'],['document','previous_document_']]);
      if(rows.some(x=>!x.reference.trim())){a.modalError('Укажите реквизиты каждого предыдущего заключения.');return;}
      s.classification=v.classification;s.commission=fd.has('commission');s.previous=rows;s.previousComplete=fd.has('previous_complete');a.event('Характер экспертизы и предыдущие заключения изменены',v.reason);
    } else if(type==='complex'){
      const selected=fd.getAll('related_works');s.groupWorks=selected.map(number=>s.groupWorks.find(x=>x.number===number)||{number,spec:number.startsWith('483')?'18.1':'16.2',closed:false});s.complex=selected.length>0;s.groupTitle=v.title||'';s.relatedClosed=s.groupWorks.every(w=>w.closed);s.checked=false;a.event('Состав комплексной группы изменён',v.reason);
    } else if(type==='timing'){
      const rows=collectRows(form,'data-delay-row',[['reason','delay_reason_'],['comment','delay_comment_'],['document','delay_document_']]);
      if(rows.some(x=>!x.reason)||new Set(rows.map(x=>x.reason)).size!==rows.length){a.modalError('Выберите разные причины длительности.');return;}
      if(v.primary&&!rows.some(x=>x.reason===v.primary)){a.modalError('Основная причина должна входить в список.');return;}
      for(const [flag,doc] of [['notification_sent','notification_document'],['extension_requested','request_document'],['deadline_breached','breach_document']])if((v[flag]==='true'||flag==='deadline_breached'&&v[flag]==='false')&&!v[doc]){a.modalError('Для указанного факта выберите подтверждающий документ либо оставьте факт неизвестным.');return;}
      s.timing={...s.timing,...v,reasons:rows,complete:fd.has('complete')};a.event('Причины длительности и подтверждения срока изменены',v.reason);
    } else if(type==='historical'||type==='activate'){
      const d=reportValue(v,form),closed=['completed','without_execution'].includes(s.status);const err=closed&&s.status!=='without_execution'?validateReport(d):'';if(err){a.modalError(err);return;}
      if(type==='activate'&&(!fd.has('complex_confirm')||!v.history_basis)){a.modalError('Проверьте комплексную группу и выберите документ-основание.');return;}
      if(type==='activate'&&closed&&(!v.history_result||!(v.completed_on||v.returned_on))){a.modalError('Для подтверждения закрытой работы нужны фактическая дата итога и итоговый документ.');return;}
      const pauses=type==='activate'?collectRows(form,'data-pause-row',[['start','historical_start_'],['end','historical_end_'],['reason','historical_reason_']]):[];
      if(pauses.some(p=>!p.start||!p.end||p.start<s.received||p.end<p.start||p.end>today||!p.reason)){a.modalError('Проверьте даты и основания подтверждённых интервалов.');return;}
      const before=JSON.stringify(s.source.result);if(closed){s.source.result=d;s.source.completed=v.completed_on||v.returned_on||'';}s.specialty=v.specialty||s.specialty;
      if(s.status==='without_execution'){s.returnReason=v.return_reason||'';s.returnComment=v.return_comment||'';}
      s.corrections.push({title:type==='activate'?'Подтверждение нового учёта':'Уточнение исторического результата',description:v.reason,before,after:JSON.stringify(s.source.result)});
      if(type==='activate'){s.source.operational=true;s.source.pausesComplete=fd.has('pauses_complete');s.pauses=pauses;s.classification=v.classification;s.commission=v.commission==='yes';s.basisId=v.history_basis;if(s.status==='suspended'&&v.open_pause){s.pause={date:v.open_pause,reason:v.reason};s.pauses.push({start:v.open_pause,end:null,reason:v.reason});}if(closed&&s.status==='completed')s.result={...d,documentId:v.history_result};}
      a.event(type==='activate'?'Старая работа подтверждена для нового учёта':'Исторические сведения уточнены',v.reason);
    } else if(type==='deadline'){
      if(!v.deadline||v.deadline<s.received){a.modalError('Укажите допустимый срок выполнения.');return;}
      if(v.event==='agreement'&&!v.deadline_document){a.modalError('Для согласованного срока выберите документ согласования.');return;}
      s.deadlineEvents.push({type:{initial:'Исходный срок',request:'Запрошенное продление',agreement:'Согласованный срок'}[v.event],date:v.date,due:v.deadline,reason:v.reason,document:v.deadline_document});if(v.event!=='request')s.deadline=v.deadline;a.event('Записано событие срока',v.reason);
    } else if(type==='return'){
      s.returnReason=v.return_reason||'';s.returnComment=v.return_comment||'';s.returnDocument=v.return_document||'';s.status='without_execution';s.checked=false;s.closures.push({kind:'without_execution',date:v.date,reason:v.reason});a.event('Возвращена без исполнения',v.reason);
    } else if(type==='prepare'||type==='package_edit'){
      if(type==='package_edit'){s.materials=v.materials||'';s.packageNote=v.package_note||'';}
      for(const w of packageWorks()){const value=v['billing_'+w.number];if(value!==undefined)s.billing[w.number]=value===''?undefined:value==='true';}
      s.paid=s.billing[s.number]===true;s.checked=false;a.event('Состав комплекта сохранён',v.reason);
    } else if(type==='attach_issue'){
      const d=a.currentDoc(v.document);if(!d){a.modalError('Выберите документ.');return;}if(v.kind!=='other'&&d.kind!==v.kind){a.modalError('Вид документа не соответствует его роли в комплекте. Выберите подходящий документ.');return;}
      if(s.packageItems.some(x=>x.id!==M().itemId&&x.document===v.document&&x.work===v.work&&x.kind===v.kind)){a.modalError('Этот документ уже включён в комплект этой работы.');return;}
      const existing=s.packageItems.find(x=>x.id===M().itemId),item={id:existing?.id||uid('item'),kind:v.kind,work:v.work,document:v.document,note:v.note||''};if(existing)Object.assign(existing,item);else s.packageItems.push(item);s.checked=false;a.event(existing?'Приложение комплекта изменено':'Документ добавлен в комплект',d.title);
    } else if(type==='check'){
      if(!s.materials.trim()){a.modalError('Опишите возвращаемые материалы.');return;}s.checked=true;s.packageChecks.push({version:s.version,reason:v.reason,documents:s.docs.map(d=>[d.id,d.versions.length]),warnings:packageWarnings()});a.event('Комплект и версии документов проверены',v.reason);
    } else if(type==='issue'){
      if(!v.recipient?.trim()||!v.basis?.trim()){a.modalError('Укажите получателя и основание получения.');return;}if(s.result?.completed_on&&v.date<s.result.completed_on){a.modalError('Выдача не может быть раньше окончания.');return;}
      s.issued={date:v.date,recipient:v.recipient,basis:v.basis,tracking:v.tracking,comment:v.comment,evidence:v.evidence,method:{personal:'Лично',post:'Почтой',courier:'Курьером'}[v.method]};a.event('Материалы выданы',v.recipient);
    } else if(type==='letter_attachment'){
      const l=s.letters.find(x=>x.id===M().letterId),d=a.currentDoc(v.document);if(!l||!d){a.modalError('Выберите документ.');return;}if(!l.attachments.includes(d.id))l.attachments.push(d.id);a.event('Добавлено приложение к письму',d.title);
    } else if(type==='letter_edit'){
      if(!v.subject?.trim()){a.modalError('Укажите тему письма.');return;}
      const old=s.letters.find(x=>x.id===M().letterId),recipients=collectRows(form,'data-recipient-row',[['name','recipient_name_'],['address','recipient_address_'],['email','recipient_email_']]);
      if(old?.registration){a.modalError('Зарегистрированное содержание заморожено. Используйте отдельные действия с письмом.');return;}
      const attachments=[...form.querySelectorAll('input[name^="letter_document"]')].map(el=>el.value).filter(Boolean);
      const l={...(old||{}),id:old?.id||uid('letter'),directionCode:v.direction,direction:v.direction==='incoming'?'Входящее':'Исходящее',department:v.department,kind:v.kind,date:v.date,number:v.number,external_on:v.external_on,received_on:v.received_on,sender:v.sender,recipient:recipients.map(x=>x.name).join(', '),recipients,subject:v.subject,body:v.body,note:v.note,parentId:M().parentId,replyCompleteness:v.replyCompleteness,attachments:[...new Set(attachments)],dispatches:old?.dispatches||[],deliveries:old?.deliveries||[]};if(old)Object.assign(old,l);else s.letters.push(l);a.event('Черновик письма сохранён',l.subject);
    } else if(type.startsWith('letter_')){
      const l=s.letters.find(x=>x.id===M().letterId);if(!l)return;
      if(type==='letter_register'){if(!v.registration_number?.trim()){a.modalError('Укажите внутренний номер.');return;}l.registration={number:v.registration_number,date:v.date,journal:v.journal};}
      if(type==='letter_receive')l.received=v.date;
      if(type==='letter_send'){if(!l.registration){a.modalError('Сначала зарегистрируйте письмо.');return;}if(!l.recipients.length){a.modalError('Добавьте адресата в черновике письма.');return;}if(!fd.getAll('recipients').length){a.modalError('Выберите адресатов этой отправки.');return;}l.sent=v.date;l.dispatches.push({date:v.date,channel:v.channel,tracking:v.tracking,recipients:fd.getAll('recipients'),evidence:v.evidence});}
      if(type==='letter_deliver'){if(!l.sent){a.modalError('Нет фактической отправки.');return;}l.deliveries.push({date:v.date,recipient:v.recipient,dispatch:v.dispatch,evidence:v.evidence});}
      if(['letter_assign','letter_control','letter_deadline'].includes(type)){if(v.due&&!v.due_basis?.trim()){a.modalError('Укажите основание срока контроля.');return;}l.control={...(l.control||{status:'open'}),responsible:v.responsible||l.control?.responsible||'',due:v.due??l.control?.due??'',basis:v.due_basis??l.control?.basis??''};}
      if(type==='letter_close'){const reply=s.letters.find(x=>x.id===v.reply);if(['reply_sent','reply_received'].includes(v.closure_reason)&&(!reply||v.closure_reason==='reply_sent'&&!reply.sent||v.closure_reason==='reply_received'&&!reply.received)){a.modalError('Для закрытия выберите ответ с подтверждённой отправкой / получением.');return;}if(v.closure_reason==='other'&&!v.comment?.trim()){a.modalError('Поясните иное основание закрытия.');return;}l.control={...l.control,status:'closed',closure_reason:v.closure_reason,reply:v.reply,comment:v.comment};}
      if(type==='letter_reopen')l.control={...l.control,status:'open'};
      a.event('Записан факт переписки',type.replace('letter_','')+' · '+l.subject);
    }
    finish(type==='historical'?'Исторические сведения уточнены. Номер, отдел и состояние сохранены.':'Изменения сохранены только в макете.');
  }
  function modalDirty(){const f=$('#modal-form')||$('#upload-form');return !!f&&!!M()?.initial&&(JSON.stringify(values(f))!==M().initial||!!M().file||!!M().files?.length);}
  function resultDirty(){return U().editing&&U().resultInitial&&JSON.stringify(U().draft)!==U().resultInitial;}
  function askDiscard(run,snapshot=null){discard={run,snapshot};a.showDialog('leave','Несохранённые изменения',`<p class="lse-small">Изменения ещё не сохранены. Продолжить редактирование или отменить ввод?</p><div class="lse-form-footer">${button('keep_editing','Продолжить редактирование',{primary:true})}${button('discard_changes','Отменить изменения')}</div>`);}
  function handleAction(action,target){
    if(a.uploading)return;
    if(revisionAttempt?.type==='uncertain'&&!['retry_save','close_dialog','keep_editing','discard_changes'].includes(action)){a.toast('Сначала повторите исходную попытку или отмените её. Ввод сохранён.');return;}
    const refusal=denied(action)||target?.dataset.denied;if(refusal){a.toast(refusal);return;}
    const id=target?.dataset.id,s=S();
    if(action==='keep_editing'){const saved=discard;discard=null;if(saved?.snapshot)restoreSnapshot(saved.snapshot);else core.closeDialog();return;}
    if(action==='discard_changes'){const saved=discard;discard=null;releaseAttempt();core.closeDialog();saved?.run();return;}
    if(action==='close_dialog'){
      if(M()?.type==='leave'){handleAction('keep_editing');return;}
      if(modalDirty()){const snapshot=formSnapshot();askDiscard(()=>closeDialog(),snapshot);}else closeDialog();return;
    }
    if(action==='cancel_result'){captureResult();if(resultDirty()){askDiscard(()=>core.handleAction(action,target));return;}core.handleAction(action,target);return;}
    if(action==='return_result'){route('work');return;}
    if(action==='refresh_card'){captureResult();render();a.toast('Сведения макета обновлены. Ввод сохранён; запросов к серверу нет.');return;}
    if(action==='retry_save'){if(revisionAttempt){const attempt=revisionAttempt;releaseAttempt();attempt.run();}return;}
    if(action==='accept_version'){if(revisionAttempt){revisionAttempt.accepted=true;const box=revisionAttempt.form.querySelector('[role="alert"]');if(box)box.textContent='Новая версия принята. Ввод сохранён; нажмите «Сохранить». ';}return;}
    if(action==='editresult'&&s.source&&!s.source.operational){historyForm(false);return;}
    if(action==='editresult'){core.handleAction(action,target);U().draft.allocations=U().draft.allocations||[];U().resultInitial=JSON.stringify(U().draft);return;}
    if(action==='pick_ref'||action==='new_ref'){pickReference(id,action==='new_ref');return;}
    if(action==='reference_new'){openUpload({kind:docContext.allowed?.[0]||'other'});return;}
    if(action==='reference_choose'){setSlot(id);return;}
    if(action==='clear_ref'){const slot=[...$('#lse-dialog').querySelectorAll('[data-doc-slot]')].find(x=>x.dataset.docSlot===id);slot.outerHTML=docSlot(id,slot.dataset.docLabel,'',slot.dataset.docKinds?slot.dataset.docKinds.split(','):null);return;}
    if(action==='add_allocation'){$('#result-allocations').insertAdjacentHTML('beforeend',allocationRow());return;}
    if(action==='history_add_allocation'){$('#history-allocations').insertAdjacentHTML('beforeend',allocationRow());return;}
    if(action==='add_delay'){$('#delay-rows').insertAdjacentHTML('beforeend',timingRow());return;}
    if(action==='add_previous'){$('#previous-rows').insertAdjacentHTML('beforeend',previousRow());return;}
    if(action==='add_historical_pause'){$('#historical-pauses').insertAdjacentHTML('beforeend',pauseRow());return;}
    if(action==='add_recipient'){$('#letter-recipients').insertAdjacentHTML('beforeend',recipientRow());return;}
    if(action==='add_letter_attachment'){const key=uid('attachment');$('#letter-attachments').insertAdjacentHTML('beforeend',`<div class="lse-repeat-row">${docSlot('letter_document_'+key,'Приложение к письму')}${button('remove_row','Убрать приложение',{text:true})}</div>`);return;}
    if(action==='remove_row'){target.closest('.lse-repeat-row').remove();refreshPrimary();return;}
    if(action==='assign'||action==='reassign'){assignmentForm(action==='reassign');return;}
    if(action==='editcase'){caseForm();return;}
    if(action==='classification'){classificationForm();return;}
    if(action==='complex'){extendedForm('complex','Редактировать комплексную группу',`${field('title','Название группы',s.groupTitle)}${['483/4-1-26','484/3-1-26'].map(number=>checkbox('related_works',number+' · '+(number.startsWith('483')?'18.1':'16.2')+' (условная работа)',s.groupWorks.some(w=>w.number===number)).replace('type="checkbox"',`type="checkbox" value="${number}"`)).join('')}<p class="lse-helper-line">${help('Связываются отдельные работы с собственными номерами. Смена состава группы не меняет номера, отделы и исполнителей.')}</p>${reasonField()}`);return;}
    if(action==='timing'){timingForm();return;}
    if(action==='historical'||action==='activate'){historyForm(action==='activate');return;}
    if(action==='source_snapshot'){sourceSnapshot();return;}
    if(action==='deadline'){extendedForm('deadline','Редактировать срок',`<div class="lse-fields">${select('event','Событие',{initial:'Установить исходный срок',request:'Запросить продление',agreement:'Согласовать новый срок'},'initial')}${field('date','Дата события',today,'date','required')}${field('deadline','Срок выполнения',s.deadline,'date','required')}</div>${docSlot('deadline_document','Документ запроса / согласования','',['deadline_request','deadline_agreement','basis'])}${reasonField()}`);return;}
    if(action==='return'){extendedForm('return','Вернуть без исполнения',`${field('date','Дата решения',today,'date','required')}${select('return_reason','Причина возврата',{'':'Не уточнена',...returns},'')}${area('return_comment','Пояснение причины')}${docSlot('return_document','Решение о возврате (необязательно)','','return_decision'.split(','))}${reasonField()}`,{},'Вернуть без исполнения');return;}
    if(action==='folder_upload'){openUpload();$('#upload-form [name="source"]').value='folder';sourceChanged();return;}
    if(action==='source_document'){openUpload();$('#upload-form [name="source"]').value='link';sourceChanged();return;}
    if(action==='sample_folder'){M().files=['Постановление.pdf','Заключение.pdf','Подписка.pdf'].map(name=>({name,type:'application/pdf',demo:true,relativePath:'482_4-1-26/'+name}));$('#upload-file').required=false;$('#upload-file-caption').textContent='Пример папки · 3 файла';batchFileRows(M().files);return;}
    if(action==='sample_file'){M().files=null;core.handleAction(action,target);return;}
    if(action==='letter'){letterForm();return;}
    if(action==='view_letter'){viewLetter(id);return;}
    if(action==='letter_edit'){letterForm(s.letters.find(l=>l.id===id));return;}
    if(action==='letter_reply'){letterForm(null,s.letters.find(l=>l.id===id));return;}
    if(action==='letter_attachment'){extendedForm('letter_attachment','Добавить приложение к письму',`${docSlot('document','Документ')}${reasonField()}`,{letterId:id});return;}
    if(action.startsWith('letter_')){letterAction(action,id);return;}
    if(action==='prepare'){extendedForm('prepare','Сохранить состав материалов',`<div class="lse-selection"><div>${h(s.materials||'Описание ещё не заполнено')}</div></div>${reasonField()}`);return;}
    if(action==='package_edit'){extendedForm('package_edit','Редактировать комплект выдачи',`${area('materials','Описание материалов',s.materials)}${area('package_note','Примечание к составу',s.packageNote)}<div class="lse-fields">${packageWorks().map(w=>select('billing_'+w.number,w.number+' · платность',{'':'Не уточнена',false:'Не платная',true:'Платная'},s.billing[w.number]===undefined?'':String(s.billing[w.number]))).join('')}</div>${reasonField()}`);return;}
    if(action==='attach_issue'){itemForm();return;}
    if(action==='edit_package_item'){itemForm(s.packageItems.find(x=>x.id===id));return;}
    if(action==='remove_package_item'){s.packageItems=s.packageItems.filter(x=>x.id!==id);s.checked=false;a.event('Приложение исключено из комплекта','Сам документ остаётся в архиве');render();return;}
    if(action==='check'){extendedForm('check','Проверить состав и версии документов',`<p class="lse-small">Будут зафиксированы текущий состав работ, окончания и версии документов. Неполный комплект файлов останется напоминанием.</p>${reasonField()}`,{},'Подтвердить проверку');return;}
    if(action==='issue'){issueForm();return;}
    if(action==='finish_related'){for(const w of s.groupWorks)w.closed=true;}
    core.handleAction(action,target);
    if(U().editing&&!U().resultInitial){U().draft.allocations=U().draft.allocations||[];U().resultInitial=JSON.stringify(U().draft);}
  }
  function refreshPrimary(){const form=$('#modal-form');if(!form||M()?.type!=='timing')return;const current=form.elements.namedItem('primary').value;const selected=[...form.querySelectorAll('[name^="delay_reason_"]')].map(el=>el.value).filter(Boolean);const primary=form.elements.namedItem('primary');primary.innerHTML='<option value="">Не указана</option>'+selected.map(code=>`<option value="${h(code)}">${h(delays[code])}</option>`).join('');primary.value=selected.includes(current)?current:'';}
  document.addEventListener('input',e=>{if(e.target.id==='ref-search')$('#ref-list').innerHTML=referenceRows(e.target.value);});
  document.addEventListener('change',e=>{
    if(e.target.name==='source'&&e.target.closest('#upload-form'))sourceChanged();
    if(e.target.id==='upload-file'&&M()){M().files=null;M().file=null;batchFileRows([...e.target.files]);}
    if(e.target.name?.startsWith('delay_reason_'))refreshPrimary();
    if(e.target.name==='kind'&&M()?.type==='attach_issue'){const slot=$('#lse-dialog [data-doc-slot="document"]');slot.outerHTML=docSlot('document','Документ','',e.target.value==='other'?null:[e.target.value]);}
    if(e.target.name?.startsWith('billing_')&&!e.target.closest('#modal-form')){S().billing[e.target.name.slice(8)]=e.target.value===''?undefined:e.target.value==='true';S().paid=S().billing[S().number]===true;S().checked=false;render();}
  });
  $('#lse-dialog').addEventListener('cancel',e=>{if(a.uploading){e.preventDefault();e.stopImmediatePropagation();return;}if(modalDirty()||docContext||viewReturn||M()?.type==='leave'){e.preventDefault();e.stopImmediatePropagation();handleAction('close_dialog');}});
  let skipLabGuard=false;
  document.addEventListener('change',e=>{
    if(skipLabGuard||!['lab-scenario','lab-profile'].includes(e.target.id))return;
    captureResult();if(!resultDirty())return;const value=e.target.value,el=e.target;el.value=el.id==='lab-profile'?U().profile:S().scenario;e.stopImmediatePropagation();askDiscard(()=>{U().editing=false;U().draft=null;skipLabGuard=true;el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));skipLabGuard=false;});
  },true);
  $('#lab-reset').addEventListener('click',e=>{if(skipLabGuard)return;captureResult();if(!resultDirty())return;e.stopImmediatePropagation();askDiscard(()=>{U().editing=false;U().draft=null;skipLabGuard=true;$('#lab-reset').click();skipLabGuard=false;});},true);
  window.addEventListener('beforeunload',e=>{captureResult();if(resultDirty()||modalDirty()||revisionAttempt){e.preventDefault();e.returnValue='';}});
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{const height=entries[0].target.getBoundingClientRect().height;document.documentElement.style.setProperty('--lse-lab-height',height+'px');}).observe($('.lse-lab'));
  return {seed,work,casePage,documentsPage,lettersPage,issuancePage,historyPage,render,denied,handleAction,submitModal,submitResult,submitUpload,openUpload,openPicker:core.openPicker,viewDocument,closeDialog,route,productionPage};
};
