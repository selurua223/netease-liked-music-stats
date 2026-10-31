(() => {
  "use strict";

  const state = {
    reports: [],
    summary: null,
    reportId: "",
    songPage: 1,
    songQuery: "",
    songSort: "title:asc",
    duplicateOnly: false,
    charts: {},
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      let detail = `请求失败：${response.status}`;
      try {
        const body = await response.json();
        const apiDetail = body.detail || body.message;
        detail = Array.isArray(apiDetail)
          ? apiDetail.map((item) => item.msg || String(item)).join("；")
          : typeof apiDetail === "string"
            ? apiDetail
            : apiDetail
              ? JSON.stringify(apiDetail)
              : detail;
      } catch {
        // Keep the HTTP status when the response is not JSON.
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function toast(message) {
    const element = $("#toast");
    element.textContent = message;
    element.classList.add("visible");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => element.classList.remove("visible"), 2600);
  }

  function switchPage(page) {
    $$(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.page === page);
    });
    $$(".page").forEach((item) => {
      item.classList.toggle("active", item.dataset.view === page);
    });
    window.location.hash = page === "dashboard" ? "" : page;
    if (page === "artists") renderArtistPageChart();
    if (page === "songs") loadSongs();
  }

  async function loadHealth() {
    try {
      const health = await api("/api/health");
      $("#healthState").textContent = `本地服务在线 · v${health.version}`;
    } catch {
      $("#healthState").textContent = "本地服务连接失败";
    }
  }

  async function loadReports(selectId = "") {
    const data = await api("/api/reports");
    state.reports = data.items || [];
    const select = $("#reportSelect");
    select.innerHTML = "";
    if (!state.reports.length) {
      select.add(new Option("尚无报告", ""));
      showNoReport();
      renderHistory();
      fillCompareOptions();
      return;
    }
    state.reports.forEach((report) => {
      const label = `${report.playlistName || "未命名歌单"} · ${formatDate(report.generatedAt)}`;
      select.add(new Option(label, report.reportId));
    });
    const targetId =
      selectId ||
      state.reportId ||
      state.reports[0].reportId;
    select.value = targetId;
    fillCompareOptions();
    await loadReport(targetId);
    renderHistory();
  }

  function showNoReport() {
    state.summary = null;
    state.reportId = "";
    $("#emptyState").hidden = false;
    $("#dashboardContent").hidden = true;
  }

  async function loadReport(reportId) {
    if (!reportId) return showNoReport();
    try {
      state.reportId = reportId;
      state.summary = await api(`/api/reports/${reportId}`);
      state.songPage = 1;
      $("#emptyState").hidden = true;
      $("#dashboardContent").hidden = false;
      renderDashboard();
      renderArtists();
      renderPortrait();
      renderDownloads();
      await loadSongs();
      requestAnimationFrame(renderCharts);
    } catch (error) {
      toast(error.message);
      showNoReport();
    }
  }

  function formatDate(value) {
    if (!value) return "时间未知";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        }).format(date);
  }

  function creatorName(creator) {
    return typeof creator === "string"
      ? creator
      : creator?.nickname || creator?.name || "未知创建者";
  }

  function renderDashboard() {
    const summary = state.summary;
    const overview = summary.overview;
    const playlist = summary.playlist;
    $("#playlistTitle").textContent = playlist.name || "未命名歌单";
    $("#playlistMeta").textContent =
      `${creatorName(playlist.creator)} · 生成于 ${formatDate(summary.metadata?.generatedAt)}`;
    $("#heroSubtitle").textContent =
      `正在查看「${playlist.name || "公开歌单"}」的本地分析报告。`;
    $("#metricSongs").textContent = overview.fetchedSongCount.toLocaleString("zh-CN");
    $("#metricSongsDetail").textContent = `缺失 ${overview.missingSongCount} 首`;
    $("#metricArtists").textContent = overview.uniqueArtists.toLocaleString("zh-CN");
    $("#metricArtistsDetail").textContent = `${overview.artistCredits.toLocaleString("zh-CN")} 次署名`;
    $("#metricDuration").textContent = overview.totalDuration;
    $("#metricPopularity").textContent =
      overview.averagePopularity == null ? "—" : Number(overview.averagePopularity).toFixed(1);

    const integrity = summary.integrity;
    const pill = $("#integrityPill");
    pill.textContent =
      integrity?.status === "complete"
        ? `完整性通过 · ${overview.fetchedSongCount}/${overview.fetchedSongCount}`
        : `部分数据 · 缺失 ${integrity?.missingCount ?? overview.missingSongCount}`;
    pill.classList.toggle("partial", integrity?.status !== "complete");

    const extremes = summary.extremes;
    const items = [
      ["时长最长", extremes.longest[0], "duration"],
      ["时长最短", extremes.shortest[0], "duration"],
      ["热度最高", extremes.hottest[0], "popularity"],
      ["热度最低", extremes.coldest[0], "popularity"],
    ];
    $("#extremeGrid").innerHTML = items
      .map(([label, song, key]) => {
        if (!song) return "";
        const value = key === "duration" ? song.duration : song.popularity;
        return `
          <div class="extreme-item">
            <span>${escapeHtml(label)}</span>
            <strong title="${escapeHtml(song.title)}">${escapeHtml(song.title)}</strong>
            <p>${escapeHtml(song.artists.join(" / "))} · ${escapeHtml(value ?? "—")}</p>
          </div>`;
      })
      .join("");
  }

  function chartText() {
    return { color: "#8d93a4", fontFamily: "Microsoft YaHei, sans-serif" };
  }

  function initChart(id) {
    const element = document.getElementById(id);
    if (!element || !window.echarts) return null;
    if (state.charts[id]) {
      state.charts[id].dispose();
    }
    const chart = window.echarts.init(element);
    state.charts[id] = chart;
    return chart;
  }

  function renderCharts() {
    if (!state.summary) return;
    const summary = state.summary;
    const top = summary.artistCounts.slice(0, 10);
    const textStyle = chartText();
    const common = {
      animationDuration: 700,
      textStyle,
      tooltip: {
        trigger: "axis",
        backgroundColor: "#171b27",
        borderColor: "rgba(255,255,255,.12)",
        textStyle: { color: "#f4f5f8" },
      },
      grid: { left: 20, right: 26, top: 20, bottom: 16, containLabel: true },
    };

    const artistChart = initChart("artistChart");
    if (artistChart) {
      artistChart.setOption({
        ...common,
        xAxis: {
          type: "category",
          data: top.map((item) => item.artist),
          axisLabel: { color: "#8d93a4", interval: 0, rotate: 20 },
          axisLine: { lineStyle: { color: "rgba(255,255,255,.08)" } },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#8d93a4" },
          splitLine: { lineStyle: { color: "rgba(255,255,255,.05)" } },
        },
        series: [
          {
            type: "bar",
            data: top.map((item) => item.count),
            barMaxWidth: 40,
            itemStyle: {
              borderRadius: [7, 7, 0, 0],
              color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "#a887ff" },
                { offset: 1, color: "#563ca9" },
              ]),
            },
          },
        ],
      });
    }

    const durationChart = initChart("durationChart");
    if (durationChart) {
      durationChart.setOption({
        ...common,
        xAxis: {
          type: "category",
          data: summary.distributions.duration.map((item) => item.label),
          axisLabel: { color: "#8d93a4", interval: 0, fontSize: 10 },
          axisLine: { lineStyle: { color: "rgba(255,255,255,.08)" } },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#8d93a4" },
          splitLine: { lineStyle: { color: "rgba(255,255,255,.05)" } },
        },
        series: [
          {
            type: "bar",
            data: summary.distributions.duration.map((item) => item.count),
            itemStyle: { color: "#58dcc8", borderRadius: [6, 6, 0, 0] },
            barMaxWidth: 36,
          },
        ],
      });
    }

    const popularityChart = initChart("popularityChart");
    if (popularityChart) {
      popularityChart.setOption({
        ...common,
        xAxis: {
          type: "category",
          data: summary.distributions.popularity.map((item) => item.label),
          axisLabel: { color: "#8d93a4", interval: 0, fontSize: 10 },
          axisLine: { lineStyle: { color: "rgba(255,255,255,.08)" } },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#8d93a4" },
          splitLine: { lineStyle: { color: "rgba(255,255,255,.05)" } },
        },
        series: [
          {
            type: "bar",
            data: summary.distributions.popularity.map((item) => item.count),
            itemStyle: { color: "#ffc65c", borderRadius: [6, 6, 0, 0] },
            barMaxWidth: 36,
          },
        ],
      });
    }
    renderArtistPageChart();
  }

  function renderArtistPageChart() {
    if (!state.summary) return;
    const top = state.summary.artistCounts.slice(0, 15);
    const chart = initChart("artistPageChart");
    if (!chart) return;
    chart.setOption({
      animationDuration: 700,
      textStyle: chartText(),
      tooltip: {
        trigger: "axis",
        backgroundColor: "#171b27",
        borderColor: "rgba(255,255,255,.12)",
        textStyle: { color: "#f4f5f8" },
      },
      grid: { left: 20, right: 25, top: 18, bottom: 14, containLabel: true },
      xAxis: {
        type: "value",
        axisLabel: { color: "#8d93a4" },
        splitLine: { lineStyle: { color: "rgba(255,255,255,.05)" } },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: top.map((item) => item.artist),
        axisLabel: { color: "#cbd0da" },
        axisLine: { show: false },
      },
      series: [
        {
          type: "bar",
          data: top.map((item) => item.count),
          barMaxWidth: 20,
          itemStyle: {
            borderRadius: [0, 7, 7, 0],
            color: new window.echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: "#b34dff" },
              { offset: 1, color: "#ff5168" },
            ]),
          },
        },
      ],
    });
  }

  function renderArtists() {
    if (!state.summary) return;
    renderArtistRows($("#artistSearch").value);
  }

  function renderArtistRows(query = "") {
    if (!state.summary) return;
    const normalized = query.trim().toLocaleLowerCase();
    const totalSongs = state.summary.overview.fetchedSongCount || 1;
    const rows = state.summary.artistCounts.filter((item) =>
      item.artist.toLocaleLowerCase().includes(normalized),
    );
    $("#artistResultCount").textContent = `${rows.length} 位歌手`;
    $("#artistTable").innerHTML = rows
      .map(
        (item, index) => `
          <tr>
            <td class="cell-muted">${index + 1}</td>
            <td class="cell-title">${escapeHtml(item.artist)}</td>
            <td>${item.count}</td>
            <td><span class="badge">${((item.count / totalSongs) * 100).toFixed(1)}%</span></td>
          </tr>`,
      )
      .join("");
  }

  async function loadSongs() {
    if (!state.reportId) return;
    const [sort, order] = state.songSort.split(":");
    const params = new URLSearchParams({
      page: String(state.songPage),
      page_size: "30",
      search: state.songQuery,
      sort,
      order,
      duplicate_only: String(state.duplicateOnly),
    });
    try {
      const data = await api(`/api/reports/${state.reportId}/songs?${params}`);
      $("#songTable").innerHTML = data.items
        .map(
          (song) => `
            <tr>
              <td class="cell-title" title="${escapeHtml(song.title)}">${escapeHtml(song.title)}</td>
              <td>${escapeHtml(song.artists.join(" / "))}</td>
              <td class="cell-muted">${escapeHtml(song.album || "—")}</td>
              <td>${escapeHtml(song.duration)}</td>
              <td>${song.popularity ?? "—"}</td>
            </tr>`,
        )
        .join("");
      $("#pageLabel").textContent = `第 ${data.page} / ${data.pages} 页 · ${data.total} 首`;
      $("#prevPage").disabled = data.page <= 1;
      $("#nextPage").disabled = data.page >= data.pages;
    } catch (error) {
      toast(error.message);
    }
  }

  function renderPortrait() {
    if (!state.summary) return;
    const overview = state.summary.overview;
    const concentration = overview.topArtistCoverage || 0;
    $("#portraitConcentration").textContent = `${concentration.toFixed(1)}%`;
    $("#concentrationBar").style.width = `${Math.min(100, concentration)}%`;
    $("#portraitConcentrationText").textContent =
      concentration >= 60
        ? "收藏高度集中在少数歌手。"
        : concentration >= 35
          ? "收藏既有关注重点，也保留了较多不同歌手。"
          : "歌手分布较分散，收藏呈现明显的长尾特征。";
    $("#portraitPopularity").textContent =
      overview.averagePopularity == null ? "—" : Number(overview.averagePopularity).toFixed(1);
    $("#portraitDuration").textContent = overview.averageDuration;
    $("#portraitDuplicates").textContent = `${overview.duplicateTitleGroups} 组`;

    const topArtists = state.summary.artistCounts.slice(0, 5).map((item) => item.artist);
    $("#portraitStory").innerHTML = `
      <p>这份收藏共有 <strong>${overview.fetchedSongCount.toLocaleString("zh-CN")}</strong> 首歌曲，
      覆盖 <strong>${overview.uniqueArtists.toLocaleString("zh-CN")}</strong> 位歌手。
      排名前五的歌手是 ${topArtists.map(escapeHtml).join("、")}。</p>
      <p>TOP 10 歌手覆盖了 <strong>${concentration.toFixed(1)}%</strong> 的歌曲。
      平均值只根据实际存在的字段计算；热度不是播放量，曲风也不会被凭空推测。</p>`;
  }

  function renderDownloads() {
    const id = encodeURIComponent(state.reportId);
    $("#exportCsv").href = `/api/reports/${id}/export?kind=songs`;
    $("#exportJson").href = `/api/reports/${id}/export?kind=summary`;
    $("#exportMd").href = `/api/reports/${id}/export?kind=markdown`;
  }

  function fillCompareOptions() {
    for (const select of [$("#compareBase"), $("#compareTarget")]) {
      select.innerHTML = "";
      state.reports.forEach((report) => {
        select.add(
          new Option(
            `${report.playlistName || "未命名歌单"} · ${formatDate(report.generatedAt)}`,
            report.reportId,
          ),
        );
      });
    }
    if (state.reports.length >= 2) {
      $("#compareBase").value = state.reports[1].reportId;
      $("#compareTarget").value = state.reports[0].reportId;
    }
  }

  function renderHistory() {
    if (!state.reports.length) {
      $("#historyList").innerHTML = '<p class="cell-muted">还没有历史报告。</p>';
      return;
    }
    $("#historyList").innerHTML = state.reports
      .map(
        (report) => `
          <div class="history-item">
            <div>
              <strong>${escapeHtml(report.playlistName || "未命名歌单")}</strong>
              <small>${formatDate(report.generatedAt)} · ${report.returnedCount} 首 · ${escapeHtml(report.integrityStatus)}</small>
            </div>
            <span class="badge">${escapeHtml(report.playlistId)}</span>
            <button data-open-report="${escapeHtml(report.reportId)}">打开</button>
          </div>`,
      )
      .join("");
    $$("[data-open-report]").forEach((button) => {
      button.addEventListener("click", () => {
        $("#reportSelect").value = button.dataset.openReport;
        loadReport(button.dataset.openReport);
        switchPage("dashboard");
      });
    });
  }

  async function startAnalysis(event) {
    event.preventDefault();
    const playlist = $("#playlistInput").value.trim();
    if (!playlist) return;
    const overlay = $("#taskOverlay");
    const progress = $("#taskProgress");
    const percent = $("#taskPercent");
    const message = $("#taskMessage");
    const title = $("#taskTitle");
    const count = $("#taskCount");
    const errorBox = $("#taskError");
    overlay.hidden = false;
    errorBox.hidden = true;
    progress.style.width = "2%";
    percent.textContent = "0%";
    try {
      const task = await api("/api/analyze", {
        method: "POST",
        body: JSON.stringify({
          playlist,
          include_raw_data: $("#includeRawData").checked,
          generate_csv: true,
        }),
      });
      title.textContent = "正在分析公开歌单";
      message.textContent = "请保持页面打开，数据只会保存在本机。";
      while (true) {
        const status = await api(`/api/tasks/${task.task_id}`);
        progress.style.width = `${status.percent || 0}%`;
        percent.textContent = `${status.percent || 0}%`;
        message.textContent = status.message;
        count.textContent =
          status.total > 0 ? `${status.completed} / ${status.total} 首` : "准备数据";
        if (status.status === "completed") {
          overlay.hidden = true;
          toast("分析完成，报告已保存到本机");
          await loadReports(status.reportId);
          switchPage("dashboard");
          return;
        }
        if (status.status === "failed") {
          throw new Error(status.error || "分析失败");
        }
        await new Promise((resolve) => setTimeout(resolve, 700));
      }
    } catch (error) {
      title.textContent = "分析未完成";
      message.textContent = "请检查公开歌单链接或网络连接，然后重试。";
      errorBox.hidden = false;
      errorBox.textContent = error.message;
      overlay.querySelector(".task-card").insertAdjacentHTML(
        "beforeend",
        '<button class="primary-button" id="closeTask" style="margin-top:18px;width:100%">关闭</button>',
      );
      $("#closeTask").addEventListener("click", () => {
        overlay.hidden = true;
        $("#closeTask")?.remove();
      });
    }
  }

  async function compareReports() {
    const base = $("#compareBase").value;
    const target = $("#compareTarget").value;
    if (!base || !target || base === target) {
      toast("请选择两份不同的报告");
      return;
    }
    try {
      const data = await api(`/api/reports/${target}/compare/${base}`);
      $("#compareResult").innerHTML = `
        <div class="compare-stat"><b>+${data.addedSongCount}</b><span>新增歌曲</span></div>
        <div class="compare-stat"><b>-${data.removedSongCount}</b><span>移除歌曲</span></div>
        <div class="compare-stat"><b>+${data.addedArtistCount}</b><span>新增歌手</span></div>
        <div class="compare-stat"><b>-${data.removedArtistCount}</b><span>移除歌手</span></div>`;
    } catch (error) {
      toast(error.message);
    }
  }

  function bindEvents() {
    $$(".nav-item").forEach((item) => {
      item.addEventListener("click", () => switchPage(item.dataset.page));
    });
    $("#analyzeForm").addEventListener("submit", startAnalysis);
    $("#openAnalyzer").addEventListener("click", () => {
      switchPage("dashboard");
      $("#playlistInput").focus();
      $("#playlistInput").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    $("#refreshReports").addEventListener("click", () => loadReports().catch((error) => toast(error.message)));
    $("#reportSelect").addEventListener("change", (event) => loadReport(event.target.value));
    $("#artistSearch").addEventListener("input", (event) => renderArtistRows(event.target.value));
    $("#songSearch").addEventListener("input", debounce((event) => {
      state.songQuery = event.target.value;
      state.songPage = 1;
      loadSongs();
    }, 250));
    $("#songSort").addEventListener("change", (event) => {
      state.songSort = event.target.value;
      state.songPage = 1;
      loadSongs();
    });
    $("#duplicatesOnly").addEventListener("change", (event) => {
      state.duplicateOnly = event.target.checked;
      state.songPage = 1;
      loadSongs();
    });
    $("#prevPage").addEventListener("click", () => {
      state.songPage = Math.max(1, state.songPage - 1);
      loadSongs();
    });
    $("#nextPage").addEventListener("click", () => {
      state.songPage += 1;
      loadSongs();
    });
    $("#compareButton").addEventListener("click", compareReports);
    window.addEventListener("resize", debounce(() => {
      Object.values(state.charts).forEach((chart) => chart.resize());
    }, 120));
  }

  function debounce(callback, delay) {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), delay);
    };
  }

  async function boot() {
    bindEvents();
    await loadHealth();
    try {
      await loadReports();
    } catch (error) {
      toast(error.message);
    }
    const initial = window.location.hash.replace("#", "") || "dashboard";
    if ($$(`[data-page="${initial}"]`).length) switchPage(initial);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
