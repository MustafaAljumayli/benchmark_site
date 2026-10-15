// Glide replay charts from one forecast round to the next.
//
// Plotly can only tween 2D lines and bars, and even then its fills and labels jump. So the slider and
// Play/Pause are driven from here: moving to a round slides every x, y and z value from where it is
// now to where that round puts it, redrawing as fast as the browser allows, then shows the round
// exactly. Lists that can't slide (different lengths) switch straight to the new round. Without this
// script the controls still work; rounds just switch instantly.
(function () {
  const GLIDE_MS = 350, PLAY_MS = 600;   // one round's slide; one round of Play, slide included
  const states = new WeakMap();          // graph -> its replay state, reset when a new figure arrives
  const turning = new WeakSet();         // 3D charts the viewer is dragging around right now

  // Plotly ships numeric arrays as base64 ({dtype, bdata}); unpack those to plain arrays.
  const TYPED = {f8: Float64Array, f4: Float32Array, i4: Int32Array, u4: Uint32Array, i2: Int16Array,
                 u2: Uint16Array, i1: Int8Array, u1: Uint8Array};
  function values(v) {
    if (v && v.bdata) {
      if (String(v.shape || "").includes(",")) return null;   // 2D grids don't slide
      const bytes = Uint8Array.from(atob(v.bdata), c => c.charCodeAt(0));
      return Array.from(new TYPED[v.dtype](bytes.buffer));
    }
    return Array.isArray(v) || ArrayBuffer.isView(v) ? Array.from(v) : null;
  }

  // Dates slide as milliseconds; everything else that isn't a number can't slide.
  const isDate = v => typeof v === "string" && /^\d{4}-\d\d-\d\d/.test(v);
  const toMs = v => Date.parse(v.length <= 10 ? v : v.replace(" ", "T") + "Z");
  const fromMs = ms => new Date(ms).toISOString().slice(0, 19);

  // Points pair up by id when the trace has ids (or map locations), otherwise by position in the list.
  function mix(a, b, t, aIds, bIds) {
    if (!a || !b) return null;
    const pair = aIds && bIds ? new Map(aIds.map((id, j) => [id, j])) : null;
    if (!pair && a.length !== b.length) return null;
    return b.map((end, i) => {
      const start = pair ? a[pair.get(bIds[i])] : a[i];
      if (typeof start === "number" && typeof end === "number" && isFinite(start) && isFinite(end))
        return start + (end - start) * t;
      if (isDate(start) && isDate(end)) return fromMs(toMs(start) + (toMs(end) - toMs(start)) * t);
      return end;
    });
  }

  function frameName(graph, index) {
    return graph.layout.sliders[0].steps[index].args[0][0];
  }

  // Positions of every moving trace in a round: {trace index: {x, y, z, ids}}.
  function positions(graph, index) {
    const frame = graph._transitionData._frameHash[frameName(graph, index)];
    const result = {};
    frame.data.forEach((trace, k) => {
      result[frame.traces ? frame.traces[k] : k] = {x: values(trace.x), y: values(trace.y), z: values(trace.z),
                                                     ids: values(trace.ids || trace.locations)};
    });
    return result;
  }

  // Draw the moving traces a fraction t of the way from where they are to the target round.
  function drawBetween(graph, state, t) {
    const traces = Object.keys(state.target).map(Number);
    const update = {x: [], y: [], z: []};
    for (const i of traces) {
      const from = state.shown[i] || {}, to = state.target[i], now = {ids: to.ids};
      for (const axis of ["x", "y", "z"]) {
        now[axis] = mix(from[axis], to[axis], t, from.ids, to.ids) || to[axis];
        update[axis].push(now[axis] || undefined);   // undefined = leave as is
      }
      state.shown[i] = now;
    }
    keepCameras(graph);
    return window.Plotly.restyle(graph, update, traces);
  }

  // Redraws put a 3D chart back at the angle saved in its layout. Save the angle the viewer has
  // turned it to first, so it stays where they are looking (even mid-drag).
  function keepCameras(graph) {
    for (const key of Object.keys(graph._fullLayout)) {
      const scene = key.startsWith("scene") && graph._fullLayout[key]._scene;
      if (scene) graph.layout[key] = Object.assign({}, graph.layout[key], {camera: scene.getCamera()});
    }
  }

  // Slide to round `index`, then show that round exactly (labels and hover text included).
  // A newer call takes over from wherever this slide has got to.
  function glideTo(graph, state, index) {
    const run = state.run = {};
    state.target = positions(graph, index);
    state.round = index;
    let begin = performance.now(), last = begin;
    return new Promise(done => {
      async function step() {
        if (state.run !== run || !isCurrent(graph, state)) return done();
        const now = performance.now();
        if (turning.has(graph)) {   // a redraw would cancel the viewer's drag: hold the slide until they let go
          begin += now - last; last = now;
          return requestAnimationFrame(step);
        }
        last = now;
        const t = Math.min((now - begin) / GLIDE_MS, 1);
        if (t < 1) {
          await drawBetween(graph, state, t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);   // ease in-out
          return requestAnimationFrame(step);
        }
        keepCameras(graph);
        await window.Plotly.animate(graph, [frameName(graph, index)], {   // redraw also moves the slider
          mode: "immediate", frame: {duration: 0, redraw: true}, transition: {duration: 0},
        }).catch(() => {});
        Object.assign(state.shown, state.target);
        done();
      }
      step();
    });
  }

  async function play(graph, state) {
    const playing = state.playing = {};
    const last = graph.layout.sliders[0].steps.length - 1;
    const first = state.round < last ? state.round + 1 : 0;   // at the end, Play starts over
    for (let i = first; i <= last && state.playing === playing && isCurrent(graph, state); i++) {
      setLayout(graph, layout => { layout.sliders[0].active = i; });
      const begin = performance.now();
      await glideTo(graph, state, i);
      await new Promise(r => setTimeout(r, Math.max(PLAY_MS - (performance.now() - begin), 0)));
    }
  }

  // False once the chart has been removed or given a new figure.
  function isCurrent(graph, state) {
    return Boolean(graph.layout && graph._fullLayout) && states.get(graph) === state;
  }

  function setUp(graph) {
    const slider = graph.layout && graph.layout.sliders && graph.layout.sliders[0];
    if (!slider || !graph._transitionData || (states.get(graph) || {}).layout === graph.layout) return;
    const round = slider.active || 0;
    states.set(graph, {layout: graph.layout, round: round, shown: positions(graph, round)});
    setLayout(graph, layout => {   // take the controls over from Plotly ("skip" = only report the click)
      layout.sliders[0].steps.forEach(step => { step.method = "skip"; });
      layout.updatemenus[0].buttons.forEach(button => { button.method = "skip"; });
    });
  }

  // Change the slider and buttons in place. Plotly.relayout would do it too, but on the site Dash answers
  // every relayout by re-plotting the whole figure, which would stop Play after one round.
  function setLayout(graph, change) {
    change(graph.layout);
    change(graph._fullLayout);
  }

  function watch(graph) {
    if (graph.dataset.replayWatched) return;
    graph.dataset.replayWatched = "yes";
    graph.on("plotly_afterplot", () => setUp(graph));
    // Dash answers every relayout (turning a 3D chart, zooming) by re-plotting the figure it was given,
    // which jumps back to the opening round and stops Play. The site doesn't use relayout data, so
    // stop Dash listening as soon as the viewer touches the chart (Dash starts listening after plotting).
    const ignoreRelayout = () => graph.removeAllListeners("plotly_relayout");
    graph.addEventListener("wheel", ignoreRelayout, true);
    graph.addEventListener("pointerdown", event => {
      ignoreRelayout();
      if (event.target.tagName === "CANVAS") turning.add(graph);   // 3D scenes draw on a canvas
    }, true);
    for (const end of ["pointerup", "pointercancel"]) window.addEventListener(end, () => turning.delete(graph));
    graph.on("plotly_sliderchange", event => {
      const state = states.get(graph);
      if (!state || !event.interaction) return;
      state.playing = null;
      glideTo(graph, state, event.slider.active);
    });
    graph.on("plotly_buttonclicked", event => {
      const state = states.get(graph);
      if (!state) return;
      if (event.button.label.includes("Play")) play(graph, state);
      else state.playing = null;
    });
    setUp(graph);
  }

  function watchAll() {
    document.querySelectorAll(".js-plotly-plot").forEach(watch);
  }

  new MutationObserver(watchAll).observe(document.body, {childList: true, subtree: true});
  watchAll();
})();
