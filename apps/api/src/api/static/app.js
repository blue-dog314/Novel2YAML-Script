/* 本地作者工作台 — Vue 3 (vendored, no build) + 原生 fetch */
const { createApp, ref, reactive, computed } = Vue;

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `HTTP ${res.status}`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

const App = {
  setup() {
    const toast = reactive({ show: false, ok: false, msg: "" });
    function notify(msg, ok = false) {
      toast.msg = msg; toast.ok = ok; toast.show = true;
      setTimeout(() => { toast.show = false; }, ok ? 2600 : 4200);
    }

    // ---- 项目区 ----
    const form = reactive({
      title: "测试小说",
      original_author: "作者",
      language: "zh",
      rights_confirmed: false,
      chapters: [
        { title: "第一章", text: "" },
        { title: "第二章", text: "" },
        { title: "第三章", text: "" },
      ],
    });
    const project = ref(null);
    const busy = reactive({});

    function addChapter() {
      form.chapters.push({ title: `第${form.chapters.length + 1}章`, text: "" });
    }
    function removeChapter(i) {
      if (form.chapters.length > 1) form.chapters.splice(i, 1);
    }

    async function createProject() {
      if (!form.rights_confirmed) { notify("请先勾选确认拥有改编/使用权"); return; }
      busy.create = true;
      try {
        const payload = {
          title: form.title,
          original_author: form.original_author,
          language: form.language,
          rights_confirmed: form.rights_confirmed,
          chapters: form.chapters.map((c) => ({ title: c.title, text: c.text })),
        };
        const data = await api("/projects", { method: "POST", body: payload });
        project.value = data;
        chapters.value = null;
        notice.value = null;
        resetGeneration();
        await loadChapters();
        notify("项目已创建", true);
      } catch (e) { notify(e.message); }
      finally { busy.create = false; }
    }

    // ---- 章节区 ----
    const chapters = ref(null);
    async function loadChapters() {
      if (!project.value) return;
      try {
        const data = await api(`/projects/${project.value.project_id}/chapters`);
        chapters.value = data.chapters;
      } catch (e) { notify(e.message); }
    }
    async function confirmChapters() {
      busy.confirm = true;
      try {
        const data = await api(`/projects/${project.value.project_id}/chapters/confirm`, { method: "POST" });
        project.value.chapters_confirmed = data.chapters_confirmed;
        await loadChapters();
        await loadNotice();
        notify("章节已确认", true);
      } catch (e) { notify(e.message); }
      finally { busy.confirm = false; }
    }

    // ---- 生成前提示 ----
    const notice = ref(null);
    async function loadNotice() {
      try {
        notice.value = await api(`/projects/${project.value.project_id}/generation-notice`);
      } catch (e) { notify(e.message); }
    }

    // ---- 生成区 ----
    const gen = reactive({
      model: "fake-model",
      output_language: "",
      target_medium: "",
      adaptation_degree: "",
    });
    const job = ref(null);
    const artifacts = ref(null);
    const history = ref([]); // {screenplay_id, label}
    const activeScreenplayId = ref(null);

    function resetGeneration() {
      job.value = null; artifacts.value = null; history.value = []; activeScreenplayId.value = null;
    }

    function buildAdaptationConfig() {
      if (!gen.output_language && !gen.target_medium && !gen.adaptation_degree) return null;
      const cfg = {};
      if (gen.output_language) cfg.output_language = gen.output_language;
      if (gen.target_medium) cfg.target_medium = gen.target_medium;
      if (gen.adaptation_degree) cfg.adaptation_degree = gen.adaptation_degree;
      return cfg;
    }

    async function loadArtifacts(screenplayId, { pushHistory = false, label = "" } = {}) {
      const data = await api(`/screenplays/${screenplayId}/artifacts`);
      artifacts.value = data;
      activeScreenplayId.value = screenplayId;
      if (pushHistory && !history.value.some((h) => h.screenplay_id === screenplayId)) {
        history.value.push({ screenplay_id: screenplayId, label: label || `初版 ${screenplayId}` });
      }
      return data;
    }

    async function generate() {
      busy.generate = true;
      try {
        const body = { project_id: project.value.project_id, model: gen.model };
        const cfg = buildAdaptationConfig();
        if (cfg) body.adaptation_config = cfg;
        const data = await api("/screenplays/generate", { method: "POST", body });
        job.value = data;
        artifacts.value = null; history.value = []; activeScreenplayId.value = null;
        if (data.status === "succeeded" && data.screenplay_id) {
          await loadArtifacts(data.screenplay_id, { pushHistory: true, label: `初版 ${data.screenplay_id}` });
          notify("生成成功", true);
        } else {
          notify(`生成失败:${data.error ? data.error.failed_stage : "未知"}`);
        }
      } catch (e) { notify(e.message); }
      finally { busy.generate = false; }
    }

    async function retryJob() {
      busy.retry = true;
      try {
        const data = await api(`/jobs/${job.value.job_id}/retry`, { method: "POST" });
        job.value = data;
        if (data.status === "succeeded" && data.screenplay_id) {
          await loadArtifacts(data.screenplay_id, { pushHistory: true, label: `重试产物 ${data.screenplay_id}` });
          notify("重试成功,已从失败阶段恢复", true);
        } else {
          notify(`重试仍失败:${data.error ? data.error.failed_stage : "未知"}`);
        }
      } catch (e) { notify(e.message); }
      finally { busy.retry = false; }
    }

    async function regenerateScene(sceneId) {
      busy[`re_${sceneId}`] = true;
      try {
        const data = await api(`/screenplays/${activeScreenplayId.value}/scenes/regenerate`, {
          method: "POST", body: { scene_id: sceneId },
        });
        artifacts.value = data;
        activeScreenplayId.value = data.screenplay_id;
        history.value.push({ screenplay_id: data.screenplay_id, label: `重生成 ${sceneId} → ${data.screenplay_id}` });
        notify(`场景 ${sceneId} 已重生成(新剧本,旧版保留)`, true);
      } catch (e) { notify(e.message); }
      finally { busy[`re_${sceneId}`] = false; }
    }

    async function switchScreenplay(screenplayId) {
      if (screenplayId === activeScreenplayId.value) return;
      try { await loadArtifacts(screenplayId); } catch (e) { notify(e.message); }
    }

    // ---- YAML 校验区 ----
    const yamlInput = ref("");
    const yamlReport = ref(null);
    async function validateYaml() {
      busy.validate = true;
      try {
        yamlReport.value = await api("/screenplays/validate-yaml", { method: "POST", body: { yaml: yamlInput.value } });
        notify("已运行校验(结果见下)", true);
      } catch (e) { notify(e.message); }
      finally { busy.validate = false; }
    }
    async function copyYaml() {
      if (!artifacts.value) return;
      try { await navigator.clipboard.writeText(artifacts.value.yaml); notify("已复制 YAML", true); }
      catch { notify("复制失败,请手动选择"); }
    }
    function useGeneratedYaml() {
      if (artifacts.value) { yamlInput.value = artifacts.value.yaml; notify("已载入生成的 YAML", true); }
    }

    // ---- schema 文档 ----
    const schemaDoc = ref(null);
    async function loadSchemaDoc() {
      if (schemaDoc.value || !activeScreenplayId.value) return;
      try {
        const data = await api(`/screenplays/${activeScreenplayId.value}/schema-doc`);
        schemaDoc.value = data.schema_doc;
      } catch (e) { notify(e.message); }
    }

    // ---- 派生 ----
    const scenes = computed(() => {
      const d = artifacts.value && artifacts.value.document;
      return d && d.screenplay && d.screenplay.scenes ? d.screenplay.scenes : [];
    });
    const report = computed(() => artifacts.value ? artifacts.value.validation_report : null);
    const reportEmpty = computed(() => {
      const r = report.value;
      return !!r && r.errors.length === 0 && r.warnings.length === 0;
    });
    const canConfirm = computed(() => project.value && !project.value.chapters_confirmed);
    const canGenerate = computed(() => project.value && project.value.chapters_confirmed);
    const jobFailed = computed(() => job.value && job.value.status === "failed");
    const canRetry = computed(() => jobFailed.value && job.value.error && job.value.error.retryable);

    return {
      toast, form, project, busy, chapters, notice, gen, job, artifacts,
      history, activeScreenplayId, yamlInput, yamlReport, schemaDoc,
      scenes, report, canConfirm, canGenerate, jobFailed, canRetry, reportEmpty,
      addChapter, removeChapter, createProject, loadChapters, confirmChapters,
      loadNotice, generate, retryJob, regenerateScene, switchScreenplay,
      validateYaml, copyYaml, useGeneratedYaml, loadSchemaDoc,
    };
  },
  template: `
  <div class="layout">
    <div class="topbar">
      <h1>小说转剧本 · 作者工作台</h1>
      <span class="sub">本地 MVP 演示界面 · 内存存储 · 无鉴权</span>
    </div>
    <div class="grid">
      <!-- 左列 -->
      <div>
        <div class="panel">
          <h2><span class="step">1</span> 创建项目</h2>
          <div class="row">
            <div><label>标题</label><input type="text" v-model="form.title" /></div>
            <div><label>原作者</label><input type="text" v-model="form.original_author" /></div>
            <div style="max-width:90px"><label>语言</label><input type="text" v-model="form.language" /></div>
          </div>
          <label>章节(至少 3 章才能生成)</label>
          <div v-for="(c, i) in form.chapters" :key="i" class="row" style="margin-bottom:6px">
            <div style="max-width:120px"><input type="text" v-model="c.title" /></div>
            <div style="flex:3"><textarea v-model="c.text" placeholder="章节正文(作为不可信数据传入)"></textarea></div>
            <div style="max-width:60px"><button class="ghost small" @click="removeChapter(i)">删除</button></div>
          </div>
          <button class="ghost small" @click="addChapter">+ 添加章节</button>
          <div class="checkbox">
            <input id="rights" type="checkbox" v-model="form.rights_confirmed" />
            <label for="rights">我已确认拥有该文本的改编/使用权</label>
          </div>
          <button :disabled="busy.create" @click="createProject">创建项目</button>
          <div v-if="project" class="spacer"></div>
          <div v-if="project" class="kv">
            <span class="k">project_id</span><span>{{ project.project_id }}</span>
            <span class="k">章节数</span><span>{{ project.chapter_count }}</span>
            <span class="k">已确认</span><span>{{ project.chapters_confirmed ? '是' : '否' }}</span>
          </div>
        </div>
        <div class="spacer"></div>
        <div class="panel" v-if="project">
          <h2><span class="step">2</span> 章节与确认</h2>
          <div v-if="chapters">
            <div v-for="ch in chapters" :key="ch.chapter_id" class="report-line">
              <span class="chip">{{ ch.order }}</span> {{ ch.title }}
              <span class="muted">· {{ ch.char_count }} 字</span>
              <span class="badge" :class="ch.confirmed ? 'ok' : 'muted'">{{ ch.confirmed ? '已确认' : '待确认' }}</span>
            </div>
            <p class="muted" style="font-size:12px">列表只显示字数,不返回原文(契约约束)。</p>
          </div>
          <button :disabled="!canConfirm || busy.confirm" @click="confirmChapters">确认章节</button>
        </div>
        <div class="spacer"></div>
        <div class="panel" v-if="notice">
          <h2><span class="step">3</span> 生成前提示</h2>
          <div class="kv">
            <span class="k">章节数</span><span>{{ notice.chapter_count }}</span>
            <span class="k">总字数</span><span>{{ notice.total_char_count }}</span>
            <span class="k">预计场景</span><span>{{ notice.estimated_scene_count }}</span>
          </div>
          <p class="muted" style="font-size:12px">{{ notice.cost_notice }}</p>
          <div v-for="(r, i) in notice.risk_notice" :key="i" class="report-line muted" style="font-size:12px">· {{ r }}</div>
        </div>
        <div class="spacer"></div>
        <div class="panel" v-if="canGenerate">
          <h2><span class="step">4</span> 生成剧本</h2>
          <div class="row">
            <div><label>model</label><input type="text" v-model="gen.model" /></div>
            <div><label>output_language</label><input type="text" v-model="gen.output_language" placeholder="可空" /></div>
          </div>
          <div class="row">
            <div><label>target_medium</label><input type="text" v-model="gen.target_medium" placeholder="可空" /></div>
            <div><label>adaptation_degree</label><input type="text" v-model="gen.adaptation_degree" placeholder="可空" /></div>
          </div>
          <div class="spacer"></div>
          <button :disabled="busy.generate" @click="generate">生成</button>
          <div v-if="jobFailed" class="spacer"></div>
          <div v-if="jobFailed" class="fail-box">
            <div class="kv">
              <span class="k">failed_stage</span><span>{{ job.error.failed_stage }}</span>
              <span class="k">error_type</span><span>{{ job.error.error_type }}</span>
              <span class="k">message</span><span>{{ job.error.error_message }}</span>
              <span class="k">suggested</span><span>{{ job.error.suggested_action }}</span>
              <span class="k">retryable</span><span>{{ job.error.retryable ? '是' : '否' }}</span>
            </div>
            <div class="spacer"></div>
            <span class="chip" v-for="a in job.error.completed_artifacts" :key="a">已完成:{{ a }}</span>
            <div class="spacer"></div>
            <button class="danger" :disabled="!canRetry || busy.retry" @click="retryJob">重试(从失败阶段恢复)</button>
            <span v-if="!canRetry" class="muted" style="font-size:12px"> · 该错误不可重试</span>
          </div>
        </div>
      </div>
      <!-- 右列 -->
      <div>
        <div class="panel" v-if="history.length">
          <h2><span class="step">5</span> 剧本产物历史</h2>
          <div v-for="h in history" :key="h.screenplay_id"
               class="history-item" :class="{ active: h.screenplay_id === activeScreenplayId }"
               @click="switchScreenplay(h.screenplay_id)">
            <span>{{ h.label }}</span>
            <span class="badge" :class="h.screenplay_id === activeScreenplayId ? 'ok' : 'muted'">
              {{ h.screenplay_id === activeScreenplayId ? '当前' : '查看' }}
            </span>
          </div>
          <p class="muted" style="font-size:12px">场景重生成会产出新剧本,旧版本保留以便对比。</p>
        </div>
        <div class="spacer" v-if="history.length"></div>
        <div class="panel" v-if="report">
          <h2>校验报告</h2>
          <span class="badge" :class="report.yaml_parse_passed ? 'ok' : 'err'">YAML 解析</span>
          <span class="badge" :class="report.schema_validation_passed ? 'ok' : 'err'">Schema</span>
          <span class="badge" :class="report.reference_validation_passed ? 'ok' : 'err'">引用</span>
          <span class="badge" :class="report.coverage_validation_passed === false ? 'err' : 'ok'">覆盖</span>
          <div class="spacer"></div>
          <div v-if="report.errors.length">
            <div v-for="(e, i) in report.errors" :key="'e'+i" class="report-line">
              <span class="badge err">err</span> <code>{{ e.code }}</code> {{ e.message }}
              <span v-if="e.path" class="path">@ {{ e.path }}</span>
            </div>
          </div>
          <div v-if="report.warnings.length">
            <div v-for="(w, i) in report.warnings" :key="'w'+i" class="report-line">
              <span class="badge warn">warn</span> <code>{{ w.code }}</code> {{ w.message }}
              <span v-if="w.path" class="path">@ {{ w.path }}</span>
            </div>
          </div>
          <div v-if="report.suggested_fixes.length">
            <div v-for="(f, i) in report.suggested_fixes" :key="'f'+i" class="report-line muted">💡 {{ f }}</div>
          </div>
          <p v-if="reportEmpty" class="muted">无错误、无警告。</p>
        </div>
        <div class="spacer" v-if="report"></div>
        <div class="panel" v-if="scenes.length">
          <h2>剧本场景</h2>
          <div v-for="sc in scenes" :key="sc.scene_id" class="scene">
            <div class="scene-head">
              <span class="scene-title">{{ sc.order }}. {{ sc.title || sc.scene_id }}</span>
              <button class="ghost small" :disabled="busy['re_'+sc.scene_id]" @click="regenerateScene(sc.scene_id)">重生成此场景</button>
            </div>
            <div class="scene-meta">
              {{ sc.scene_id }} · 源章节 {{ (sc.source_chapters || []).join(', ') }}
              <span v-if="sc.summary">· {{ sc.summary }}</span>
            </div>
            <div v-for="b in sc.content_blocks" :key="b.block_id" class="block" :class="b.type">
              <span class="ty">{{ b.type }}</span>
              <template v-if="b.type === 'dialogue'">
                <span class="speaker">{{ b.speaker_name }}</span>
                <span v-if="b.emotion" class="emotion">（{{ b.emotion }}）</span>:
                <span class="text">{{ b.line }}</span>
                <span v-if="b.action_hint" class="muted"> [{{ b.action_hint }}]</span>
              </template>
              <span v-else class="text">{{ b.text }}</span>
            </div>
          </div>
        </div>
        <div class="spacer" v-if="scenes.length"></div>
        <div class="panel" v-if="artifacts">
          <h2>导出 YAML</h2>
          <textarea class="mono" rows="10" readonly :value="artifacts.yaml"></textarea>
          <div class="spacer"></div>
          <button class="ghost small" @click="copyYaml">复制</button>
          <button class="ghost small" @click="useGeneratedYaml">载入到下方校验框</button>
        </div>
        <div class="spacer"></div>
        <div class="panel">
          <h2><span class="step">6</span> 校验我的 YAML</h2>
          <p class="muted" style="font-size:12px">粘贴作者编辑后的 YAML,运行四层校验。该接口不存储传入内容。</p>
          <textarea class="mono" rows="8" v-model="yamlInput" placeholder="metadata: ..."></textarea>
          <div class="spacer"></div>
          <button :disabled="busy.validate" @click="validateYaml">校验</button>
          <div v-if="yamlReport" class="spacer"></div>
          <div v-if="yamlReport">
            <span class="badge" :class="yamlReport.yaml_parse_passed ? 'ok' : 'err'">YAML 解析</span>
            <span class="badge" :class="yamlReport.schema_validation_passed ? 'ok' : 'err'">Schema</span>
            <span class="badge" :class="yamlReport.reference_validation_passed ? 'ok' : 'err'">引用</span>
            <span class="badge" :class="yamlReport.coverage_validation_passed === false ? 'err' : 'ok'">覆盖</span>
            <div class="spacer"></div>
            <div v-for="(e, i) in yamlReport.errors" :key="'ye'+i" class="report-line">
              <span class="badge err">err</span> <code>{{ e.code }}</code> {{ e.message }}
              <span v-if="e.path" class="path">@ {{ e.path }}</span>
            </div>
            <div v-for="(w, i) in yamlReport.warnings" :key="'yw'+i" class="report-line">
              <span class="badge warn">warn</span> <code>{{ w.code }}</code> {{ w.message }}
            </div>
            <div v-for="(f, i) in yamlReport.suggested_fixes" :key="'yf'+i" class="report-line muted">💡 {{ f }}</div>
          </div>
        </div>
        <div class="spacer"></div>
        <div class="panel" v-if="activeScreenplayId">
          <details @toggle="loadSchemaDoc">
            <summary>查看 schema 字段语义文档</summary>
            <pre class="schema" v-if="schemaDoc">{{ schemaDoc }}</pre>
            <p v-else class="muted">加载中…</p>
          </details>
        </div>
      </div>
    </div>
    <div v-if="toast.show" class="toast" :class="{ ok: toast.ok }">{{ toast.msg }}</div>
  </div>
  `,
};

createApp(App).mount("#app");
