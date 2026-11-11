"""Terminal recording, playback and export commands"""

from __future__ import annotations

from pathlib import Path

import click


@click.group()
def termshow():
    """Terminal recording and playback for CLI/TUI documentation.

    Record terminal sessions, edit them with YAML scripts, and render
    them as SVG frame sequences for the termshow player.
    """
    pass


@click.command("record")
@click.argument("output", type=click.Path(), required=False)
@click.option(
    "--steps",
    "steps_file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Run the steps in this .termshow.yml script instead of recording live",
)
@click.option("--cols", type=int, default=None, help="Terminal width in columns")
@click.option("--rows", type=int, default=None, help="Terminal height in rows")
@click.option("--shell", type=str, default=None, help="Shell to spawn (default: $SHELL)")
@click.option("--capture-input", is_flag=True, help="Also capture keyboard input events")
def term_record(
    output: str | None,
    steps_file: str | None,
    cols: int | None,
    rows: int | None,
    shell: str | None,
    capture_input: bool,
) -> None:
    """Record a terminal session to a .termshow file.

    Spawns an interactive shell and captures all output with timing.
    Press Ctrl+D or type 'exit' to stop recording.

    With --steps, nothing is typed by hand: the script's `steps:` are run in
    a hidden terminal and the session is saved. OUTPUT defaults to the
    recording the script belongs to (demo.termshow for demo.termshow.yml),
    and --cols, --rows, and --shell override the script's `record:` settings.

    Examples:
      great-docs termshow record docs/assets/install.termshow
      great-docs termshow record --steps docs/assets/install.termshow.yml
    """
    if steps_file:
        _record_steps(steps_file, output, cols=cols, rows=rows, shell=shell)
        return
    if output is None:
        raise click.UsageError("Missing argument 'OUTPUT'.")

    from .._term_player.recorder import record_session

    if not output.endswith(".termshow"):
        output += ".termshow"

    record_session(output, shell=shell, cols=cols, rows=rows, capture_input=capture_input)


def _record_steps(
    steps_file: str, output: str | None, *, cols: int | None, rows: int | None, shell: str | None
) -> None:
    """`termshow record --steps`: run a script's steps and save the recording."""
    from dataclasses import replace

    from .._term_player.importer import _write_termshow
    from .._term_player.steps import StepsError, load_steps, record_steps

    script_path = Path(steps_file)
    if output is None:
        if not script_path.name.endswith(".termshow.yml"):
            raise click.UsageError(
                f"Give an OUTPUT path: {script_path.name} isn't named NAME.termshow.yml"
            )
        output_path = script_path.with_name(script_path.name[: -len(".yml")])
    else:
        output_path = Path(output if output.endswith(".termshow") else output + ".termshow")

    try:
        settings, steps = load_steps(script_path)
    except StepsError as e:
        raise click.ClickException(str(e)) from None
    overrides = {"cols": cols, "rows": rows, "shell": shell}
    settings = replace(settings, **{k: v for k, v in overrides.items() if v is not None})

    def progress(i: int, step) -> None:
        click.secho(f"  {i + 1}/{len(steps)} {step.describe()}", dim=True, err=True)

    count = f"{len(steps)} step{'' if len(steps) == 1 else 's'}"
    click.echo(f"Running {count} from {script_path} in {settings.shell!r}", err=True)
    try:
        recording = record_steps(settings, steps, title=output_path.stem, on_step=progress)
    except StepsError as e:
        click.echo(f"✗ {e}", err=True)
        if e.screen:
            click.echo("\nThe screen at the time:", err=True)
            for line in e.screen.splitlines():
                click.echo(f"  │ {line}", err=True)
        raise SystemExit(1) from None

    _write_termshow(recording, output_path)
    click.echo(
        f"✓ Recorded {output_path} ({recording.duration:.1f}s, {len(recording.events)} events)"
    )


@click.command("render")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--output-dir", "-o", type=click.Path(), default=None, help="Output directory for frames"
)
@click.option("--interval", type=float, default=2.0, help="Keyframe interval in seconds")
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
def term_render(source: str, output_dir: str | None, interval: float, script: str | None) -> None:
    """Render a .termshow recording into SVG frames.

    Processes the recording through the virtual terminal emulator and
    produces SVG keyframes + a manifest.json for the player, along with
    the recording's transcript (_transcript.md).
    """
    from .._term_player.prerender import load_recording, render_recording
    from .._term_player.prerender import output_dir as recording_output_dir

    source_path = Path(source)
    recording, script_obj = load_recording(source_path, Path(script) if script else None)
    if output_dir is None:
        # The shortcode's fallback expects output beside the recording in
        # `termshow/<name>/`.
        output_dir = str(recording_output_dir(source_path, source_path.parent, source_path.parent))
    manifest = render_recording(recording, script_obj, Path(output_dir), keyframe_interval=interval)

    stats = manifest.stats
    click.echo(
        f"✓ Rendered {stats.keyframes} keyframes ({stats.frames} unique screens) to {output_dir}/"
    )
    click.echo(f"  Duration: {manifest.duration:.1f}s | Chapters: {len(manifest.chapters)}")
    click.echo(f"  Page payload: {stats.manifest_bytes / 1024:.1f} KB")


@click.command("import-cast")
@click.argument("source", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
def term_import_cast(source: str, output: str) -> None:
    """Import an asciicast (.cast) file to .termshow format."""
    from .._term_player.importer import import_asciicast

    if not output.endswith(".termshow"):
        output += ".termshow"

    recording = import_asciicast(source, output)
    click.echo(f"✓ Imported {source} → {output}")
    click.echo(f"  Duration: {recording.duration:.1f}s | Events: {len(recording.events)}")


@click.command("import-tape")
@click.argument("tape", type=click.Path(exists=True, dir_okay=False))
@click.argument("output", type=click.Path(), required=False)
@click.option("--record", "record_now", is_flag=True, help="Record the script once it's written")
@click.option("--force", is_flag=True, help="Overwrite OUTPUT if it exists")
def term_import_tape(tape: str, output: str | None, record_now: bool, force: bool) -> None:
    """Convert a VHS .tape file to a .termshow.yml script with steps.

    Each tape command becomes a step or a setting. Commands with no
    Termshow equivalent, such as Output or Set FontSize, are listed, and
    left as comments at the top of the script. OUTPUT defaults to
    demo.termshow.yml for demo.tape.

    Examples:
      great-docs termshow import-tape demo.tape
      great-docs termshow import-tape demo.tape docs/assets/demo.termshow.yml --record
    """
    from .._term_player.tape import TapeError, convert_tape

    tape_path = Path(tape)
    if output is None:
        output_path = tape_path.with_name(tape_path.stem + ".termshow.yml")
    elif output.endswith(".termshow.yml"):
        output_path = Path(output)
    else:
        output_path = Path(output.removesuffix(".termshow") + ".termshow.yml")
    if output_path.exists() and not force:
        raise click.ClickException(f"{output_path} already exists (use --force to replace it)")

    try:
        script = convert_tape(tape_path)
    except TapeError as e:
        raise click.ClickException(f"{tape_path.name}, {e}") from None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        script.to_yaml(source_name=tape_path.name, script_name=str(output_path)),
        encoding="utf-8",
    )

    count = len(script.steps)
    click.echo(f"✓ Converted {tape} → {output_path} ({count} step{'' if count == 1 else 's'})")
    if script.skipped:
        click.echo("  Not converted:")
        for skipped in script.skipped:
            click.echo(f"    line {skipped.line}: {skipped.text} ({skipped.reason})")

    if record_now:
        _record_steps(str(output_path), None, cols=None, rows=None, shell=None)
    else:
        click.echo(f"  Record it with: great-docs termshow record --steps {output_path}")


@click.command("play")
@click.argument("source", type=click.Path(exists=True))
@click.option("--speed", type=float, default=1.0, help="Playback speed multiplier")
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_play(source: str, speed: float, script: str | None, no_script: bool) -> None:
    """Play a recording directly in the terminal.

    Applies the companion .termshow.yml script (cuts and speed changes) unless
    --no-script is given. Accepts .termshow and asciicast (.cast) files. Press
    Ctrl+C to stop.

    Examples:
      great-docs termshow play demos/install.termshow
      great-docs termshow play demos/install.termshow --speed 2
    """
    from .._term_player import apply_script
    from .._term_player.playback import play_recording
    from .._term_player.prerender import load_recording

    if speed <= 0:
        raise click.BadParameter("must be greater than 0", param_hint="--speed")

    recording, script_obj = load_recording(
        Path(source), Path(script) if script else None, use_script=not no_script
    )
    if script_obj is not None:
        recording = apply_script(recording, script_obj)

    try:
        play_recording(recording, speed=speed)
    except KeyboardInterrupt:
        click.echo("\n✓ Playback stopped.")


@click.command("export")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--svg",
    "fmt",
    flag_value="svg",
    default=True,
    help="Write an animated SVG (the default)",
)
@click.option(
    "--cast",
    "fmt",
    flag_value="cast",
    help="Write an asciicast file for asciinema (version 3 unless --v2 is given)",
)
@click.option("--gif", "fmt", flag_value="gif", help="Write an animated GIF (needs ffmpeg)")
@click.option("--mp4", "fmt", flag_value="mp4", help="Write an MP4 video (needs ffmpeg)")
@click.option("--webm", "fmt", flag_value="webm", help="Write a WebM video (needs ffmpeg)")
@click.option(
    "--bundle",
    "fmt",
    flag_value="bundle",
    help="Write a bundle for the Termshow player: the recording in one .termshow.json file",
)
@click.option("--v2", is_flag=True, help="With --cast, write asciicast version 2")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file (default: the recording's name with the format's extension, or "
    ".termshow.json for a bundle). Its extension picks the format when no format option is "
    "given",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
@click.option("--no-loop", is_flag=True, help="Play once and stop on the last screen")
@click.option(
    "--end-pause",
    type=float,
    default=2.0,
    show_default=True,
    help="Seconds to hold the last screen before looping",
)
@click.option("--chapter-cards", is_flag=True, help="Show a title card at each chapter")
@click.option("--no-annotations", is_flag=True, help="Leave out the script's annotations")
@click.option(
    "--font-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Embed this .woff2/.woff/.ttf/.otf font for the terminal text",
)
@click.option(
    "--fps",
    type=click.IntRange(min=1, max=60),
    default=None,
    help="Frames per second of a GIF or video  [default: 20 for GIF, 30 for video]",
)
@click.option(
    "--scale",
    type=float,
    default=None,
    help="Pixels per SVG unit in a GIF or video  [default: 1 for GIF, 2 for video]",
)
@click.option(
    "--max-idle",
    type=float,
    default=None,
    help="Shorten pauses longer than this many seconds in a GIF or video",
)
@click.pass_context
def term_export(
    ctx: click.Context,
    source: str,
    fmt: str,
    v2: bool,
    output: str | None,
    script: str | None,
    no_script: bool,
    no_loop: bool,
    end_pause: float,
    chapter_cards: bool,
    no_annotations: bool,
    font_file: str | None,
    fps: int | None,
    scale: float | None,
    max_idle: float | None,
) -> None:
    """Export a recording as an animated SVG, a GIF or video, an asciicast file, or a bundle.

    The SVG plays with CSS alone, so it works as an image in a GitHub or
    GitLab README. The companion .termshow.yml script's cuts, speed changes,
    chapters, and annotations are applied unless --no-script is given.

    With --gif, --mp4, or --webm, each screen is drawn like a screenshot
    and ffmpeg joins them, for places that can't show an animated SVG, such
    as pull request comments, chat, and slides. This needs ffmpeg and
    rsvg-convert (or resvg).

    With a light/dark theme pair, two files are written (NAME-light and
    NAME-dark), along with a <picture> snippet that picks one by the
    reader's color scheme (for SVG and GIF).

    With --cast, the recording is written for asciinema's player, CLI, and
    asciinema.org. The script's cuts and speed changes are applied, its
    chapters become markers, and its theme (the light side of a pair) is
    kept. Annotations, highlights, and snippets are left out.

    With --bundle, the recording is written as one .termshow.json file
    with everything the Termshow player needs, including the transcript.
    Point a <termshow-player> element's src at it, or the termshow
    shortcode's file.

    Examples:
      great-docs termshow export demos/install.termshow
      great-docs termshow export demos/install.termshow --svg -o install.svg
      great-docs termshow export demos/install.termshow --gif --max-idle 2
      great-docs termshow export demos/install.termshow -o install.mp4
      great-docs termshow export demos/install.termshow --cast
      great-docs termshow export demos/install.termshow --bundle
    """
    from .._term_player import apply_script, generate_manifest
    from .._term_player.bundle import BUNDLE_SUFFIX
    from .._term_player.export import SIZE_WARNING_BYTES, export_svg, picture_snippet
    from .._term_player.prerender import load_recording
    from .._term_player.video import VIDEO_FORMATS

    # The file extension of each format, and the format of each extension
    extensions = {"bundle": BUNDLE_SUFFIX.lstrip(".")}
    formats = {"json": "bundle"}
    suffix = Path(output).suffix.lower().lstrip(".") if output else ""
    named = formats.get(suffix, suffix)
    if ctx.get_parameter_source("fmt") == click.core.ParameterSource.DEFAULT:
        if named in (*VIDEO_FORMATS, "cast", "bundle"):
            fmt = named
    elif named in (*VIDEO_FORMATS, "svg", "cast", "bundle") and named != fmt:
        raise click.UsageError(
            f"--{fmt} writes a .{extensions.get(fmt, fmt)} file, but -o ends in .{suffix}"
        )

    # The formats each option applies to
    applies = {
        "--no-loop": (no_loop, ("svg", "gif")),
        "--end-pause": (end_pause != 2.0, ("svg", *VIDEO_FORMATS)),
        "--chapter-cards": (chapter_cards, ("svg",)),
        "--no-annotations": (no_annotations, ("svg", *VIDEO_FORMATS)),
        "--font-file": (font_file, ("svg",)),
        "--fps": (fps is not None, VIDEO_FORMATS),
        "--scale": (scale is not None, VIDEO_FORMATS),
        "--max-idle": (max_idle is not None, VIDEO_FORMATS),
        "--v2": (v2, ("cast",)),
    }
    for name, (given, formats) in applies.items():
        if given and fmt not in formats:
            names = [f"--{f}" for f in formats]
            listed = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
            raise click.UsageError(f"{name} only applies to {listed}")
    if end_pause < 0:
        raise click.BadParameter("can't be negative", param_hint="--end-pause")
    if scale is not None and scale <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--scale")
    if max_idle is not None and max_idle <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--max-idle")

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )

    out_path = Path(output) if output else source_path.with_suffix(f".{extensions.get(fmt, fmt)}")
    if fmt == "cast":
        _export_cast(recording, script_obj, source_path, out_path, version=2 if v2 else 3)
        return
    if fmt == "bundle":
        _export_bundle(recording, script_obj, out_path)
        return

    if script_obj is not None:
        recording = apply_script(recording, script_obj)
    manifest = generate_manifest(recording, script_obj)

    if fmt in VIDEO_FORMATS:
        options = dict(
            fps=fps,
            scale=scale,
            loop=not no_loop,
            end_pause=end_pause,
            annotations=not no_annotations,
            max_idle=max_idle,
        )
        _export_video(manifest, out_path, fmt, options)
        return

    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{out_path.suffix}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{out_path.suffix}"), True),
        ]
    else:
        sides = [(out_path, False)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    for path, dark in sides:
        try:
            svg = export_svg(
                manifest,
                dark=dark,
                loop=not no_loop,
                end_pause=end_pause,
                chapter_cards=chapter_cards,
                annotations=not no_annotations,
                font_file=font_file,
            )
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        path.write_text(svg, encoding="utf-8")
        size = len(svg.encode("utf-8"))
        click.echo(f"✓ Exported {path} ({size / 1024:.1f} KB)")
        if size > SIZE_WARNING_BYTES:
            click.echo(
                f"  Warning: over {SIZE_WARNING_BYTES // (1024 * 1024)} MB, which README "
                "viewers can be slow to play. Cutting idle stretches or long scrolling "
                "output (cuts, speed_map) in the script makes it smaller.",
                err=True,
            )

    click.echo(
        f"  Duration: {manifest.duration:.1f}s | Unique screens: {len(manifest.frames)}"
        f" | Unique rows: {len(manifest.lines)}"
    )
    if len(sides) == 2:
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the recording should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


def _export_video(manifest, out_path: Path, fmt: str, options: dict) -> None:
    """Write `termshow export --gif/--mp4/--webm`'s files and report what went into them."""
    from .._term_player.export import picture_snippet
    from .._term_player.video import SIZE_WARNING_BYTES, VideoError, export_video

    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{out_path.suffix}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{out_path.suffix}"), True),
        ]
    else:
        sides = [(out_path, False)]

    for path, dark in sides:
        try:
            result = export_video(manifest, path, fmt, dark=dark, **options)
        except (VideoError, ValueError) as e:
            raise click.ClickException(str(e)) from e
        size = path.stat().st_size
        click.echo(f"✓ Exported {path} ({size / 1024:.1f} KB, {result.width}×{result.height})")
        if size > SIZE_WARNING_BYTES:
            click.echo(
                f"  Warning: over {SIZE_WARNING_BYTES // (1024 * 1024)} MB, which GitHub won't "
                "take in an issue or pull request. A lower --fps or --scale, --max-idle, or "
                "cuts in the script make it smaller.",
                err=True,
            )

    click.echo(
        f"  Duration: {result.duration:.1f}s | Frames: {result.stills}"
        f" | Unique images: {result.images}"
    )
    if len(sides) == 2 and fmt == "gif":
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the recording should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


def _export_bundle(recording, script, out_path: Path) -> None:
    """Write `termshow export --bundle`'s file and report what went into it."""
    from .._term_player.bundle import make_bundle

    manifest, text = make_bundle(recording, script)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    click.echo(f"✓ Exported {out_path} ({len(text.encode()) / 1024:.1f} KB)")
    click.echo(
        f"  Duration: {manifest.duration:.1f}s | Unique screens: {len(manifest.frames)}"
        f" | Unique rows: {len(manifest.lines)}"
    )
    click.echo(f'\nPlay it with <termshow-player src="{out_path.name}"></termshow-player>')


def _export_cast(recording, script, source_path: Path, out_path: Path, *, version: int) -> None:
    """Write `termshow export --cast`'s file and report what went into it."""
    from .._term_player.cast import export_asciicast, left_out

    if out_path.resolve() == source_path.resolve():
        raise click.UsageError(
            f"{out_path} is the recording being exported; choose another name with -o"
        )
    text = export_asciicast(recording, script, version=version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    import json

    codes = [json.loads(line)[1] for line in text.splitlines()[1:]]
    events, markers = len(codes), codes.count("m")
    click.echo(f"✓ Exported {out_path} (asciicast v{version}, {len(text.encode()) / 1024:.1f} KB)")
    summary = f"  Events: {events}"
    if markers:
        summary += f" | Markers: {markers}"
    click.echo(summary)
    if script is not None and script.dark_theme is not None:
        click.echo("  The script's theme is a light/dark pair; the light side was used.")
    missing = left_out(script)
    if missing:
        click.echo(f"  Left out (they need the Termshow player): {', '.join(missing)}.", err=True)


@click.command("snap")
@click.argument("source", type=click.Path(exists=True))
@click.option("--at", "at", type=float, default=None, help="Playback time in seconds")
@click.option("--chapter", default=None, help="Take the last screen of the chapter with this label")
@click.option("--end", is_flag=True, help="Take the last screen (the default)")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output .svg or .png file (default: the recording's name with -snap.svg)",
)
@click.option("--png", is_flag=True, help="Write a PNG (needs rsvg-convert or resvg)")
@click.option(
    "--scale",
    type=float,
    default=None,
    help="Pixels per SVG unit in a PNG  [default: 2]",
)
@click.option("--annotations", is_flag=True, help="Draw the annotations showing at that moment")
@click.option(
    "--font-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Embed this .woff2/.woff/.ttf/.otf font for the terminal text (SVG only)",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_snap(
    source: str,
    at: float | None,
    chapter: str | None,
    end: bool,
    output: str | None,
    png: bool,
    scale: float | None,
    annotations: bool,
    font_file: str | None,
    script: str | None,
    no_script: bool,
) -> None:
    """Take a screenshot of one moment in a recording.

    The screenshot is a still SVG, or a PNG with --png or an -o name ending
    in .png, for poster images, social cards, and slides. It uses the
    companion .termshow.yml script's cuts, speed changes, theme, window
    chrome, and prompt replacement unless --no-script is given, and --at
    is a time on the resulting playback timeline.

    With a light/dark theme pair, two files are written (NAME-light and
    NAME-dark), along with a <picture> snippet that picks one by the
    reader's color scheme.

    Examples:
      great-docs termshow snap demos/install.termshow
      great-docs termshow snap demos/install.termshow --at 12.5 -o shot.svg
      great-docs termshow snap demos/install.termshow --chapter Install --png
    """
    from .._term_player import apply_script, generate_manifest
    from .._term_player.export import picture_snippet
    from .._term_player.prerender import load_recording
    from .._term_player.snap import SnapError, rasterize, snap_svg, snap_time

    if sum([at is not None, chapter is not None, end]) > 1:
        raise click.UsageError("use only one of --at, --chapter, and --end")
    if output is not None:
        suffix = Path(output).suffix.lower()
        if suffix not in (".svg", ".png"):
            raise click.UsageError(f"-o must end in .svg or .png, got {output!r}")
        if png and suffix == ".svg":
            raise click.UsageError("--png writes a PNG, but -o ends in .svg")
        png = png or suffix == ".png"
    if not png:
        if scale is not None:
            raise click.UsageError("--scale only applies to PNG output")
    elif font_file is not None:
        raise click.UsageError("--font-file only applies to SVG output")
    if scale is not None and scale <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--scale")

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )
    if script_obj is not None:
        recording = apply_script(recording, script_obj)
    manifest = generate_manifest(recording, script_obj)

    try:
        time = snap_time(manifest, at=at, chapter=chapter)
    except SnapError as e:
        raise click.UsageError(str(e)) from e

    ext = ".png" if png else ".svg"
    out_path = Path(output) if output else source_path.with_name(f"{source_path.stem}-snap{ext}")
    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{ext}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{ext}"), True),
        ]
    else:
        sides = [(out_path, False)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    for path, dark in sides:
        try:
            svg = snap_svg(manifest, time, dark=dark, annotations=annotations, font_file=font_file)
            if png:
                rasterize(svg, path, scale=2.0 if scale is None else scale)
            else:
                path.write_text(svg, encoding="utf-8")
        except (SnapError, ValueError) as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"✓ Saved {path} ({path.stat().st_size / 1024:.1f} KB)")

    click.echo(f"  At {time:.2f}s of {manifest.duration:.2f}s")
    if len(sides) == 2:
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the screenshot should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


@click.command("transcript")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--markdown",
    "fmt",
    flag_value="markdown",
    default=True,
    help="Write the recording's text as Markdown (the default)",
)
@click.option("--vtt", "fmt", flag_value="vtt", help="Write the annotations as WebVTT captions")
@click.option(
    "--vtt-chapters", "fmt", flag_value="chapters", help="Write the chapters as a WebVTT track"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file (default: print to the terminal)",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_transcript(
    source: str, fmt: str, output: str | None, script: str | None, no_script: bool
) -> None:
    """Write the text of a recording, or captions for it.

    The transcript holds everything the recording shows, including lines
    that scroll away, as plain text without colors. The companion
    .termshow.yml script's chapters split it into sections, its annotations
    become notes, and its prompt replacement is applied, unless --no-script
    is given. A full-screen program, like less or vim, keeps only its last
    screen.

    With --vtt, the annotations are written as WebVTT captions; with
    --vtt-chapters, the chapters are written as a WebVTT chapters track.
    Both are on the playback timeline (after cuts and speed changes).

    Great Docs builds write each recording's transcript next to its player,
    for screen readers, search, and the page's Markdown version.

    Examples:
      great-docs termshow transcript demos/install.termshow
      great-docs termshow transcript demos/install.termshow -o install.md
      great-docs termshow transcript demos/install.termshow --vtt -o install.vtt
    """
    from .._term_player.prerender import load_recording
    from .._term_player.transcript import transcript_markdown, transcript_vtt

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )
    if fmt == "markdown":
        text = transcript_markdown(recording, script_obj)
        empty = "The recording shows no text." if not text else ""
    else:
        text = transcript_vtt(recording, script_obj, chapters=fmt == "chapters")
        what = "chapters" if fmt == "chapters" else "annotations"
        empty = f"The recording has no {what}." if "-->" not in text else ""

    if output is None:
        click.echo(text, nl=False)
    else:
        out_path = Path(output)
        if out_path.resolve() == source_path.resolve():
            raise click.UsageError(f"{out_path} is the recording itself; choose another name")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        click.echo(f"✓ Wrote {out_path} ({len(text.encode()) / 1024:.1f} KB)")
    if empty:
        click.echo(empty, err=True)


@click.command("validate")
@click.argument("sources", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--script",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to .termshow.yml script (with a single recording)",
)
@click.option("--no-script", is_flag=True, help="Check the recording without its script")
@click.option("--strict", is_flag=True, help="Fail on warnings as well as errors")
def term_validate(
    sources: tuple[str, ...], script: str | None, no_script: bool, strict: bool
) -> None:
    """Check recordings and their scripts for mistakes.

    Errors are things the format doesn't allow: a malformed recording line,
    an unknown script key, a misspelled theme or position, a cut that ends
    before it starts, or a pattern that isn't a regular expression.

    Warnings are things that are allowed but probably not meant: an
    annotation that starts after the recording ends, overlapping cuts or
    snippets, chapters out of order, two annotations in the same spot, or a
    `match` pattern that never appears on screen while it's active.

    Each recording's companion .termshow.yml is checked with it. A script can
    also be given on its own, and its recording is found next to it. Exits
    with status 1 if there are errors (or, with --strict, warnings).

    Examples:
      great-docs termshow validate demos/install.termshow
      great-docs termshow validate demos/*.termshow --strict
    """
    from .._term_player.validate import ERROR, check_script_text, validate

    if script and len(sources) > 1:
        raise click.BadParameter("use it with a single recording", param_hint="--script")

    errors = warnings = 0
    for source in sources:
        source_path = Path(source)
        script_for = script
        if source_path.name.endswith(".termshow.yml"):
            script_for = script or source
            source_path = source_path.with_name(source_path.name[: -len(".yml")])
            if not source_path.exists() and not _has_steps(script_for):
                raise click.ClickException(f"No recording {source_path} for the script {source}")
        if source_path.exists():
            problems = validate(source_path, script_for, use_script=not no_script)
            checked = str(source_path)
        else:
            # A script with steps that hasn't been recorded yet is checked on its own
            script_path = Path(script_for)
            problems = []
            check_script_text(script_path.read_text(encoding="utf-8"), script_path.name, problems)
            checked = f"{script_path} (not recorded yet)"
        if not problems:
            click.echo(f"✓ {checked}: no problems")
        for problem in problems:
            click.echo(f"{problem.severity}: {problem}")
        errors += sum(1 for p in problems if p.severity == ERROR)
        warnings += sum(1 for p in problems if p.severity != ERROR)

    if errors or warnings:
        plural = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"  # noqa: E731
        click.echo(f"\n{plural(errors, 'error')}, {plural(warnings, 'warning')}")
    if errors or (strict and warnings):
        raise SystemExit(1)


def _has_steps(script: str) -> bool:
    """Whether a script has a `steps:` section, so it can be recorded from."""
    from yaml12 import parse_yaml

    try:
        data = parse_yaml(Path(script).read_text(encoding="utf-8"))
    except ValueError:
        return False
    return isinstance(data, dict) and "steps" in data


@click.command("check")
@click.argument("scripts", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--ignore",
    "ignore",
    multiple=True,
    metavar="REGEX",
    help="Leave text matching this pattern out of the comparison (repeatable)",
)
@click.option("--update", is_flag=True, help="Re-record the recordings that have drifted")
@click.option("--shell", type=str, default=None, help="Run the steps in this shell instead")
@click.option(
    "--json", "as_json", is_flag=True, help="Print the results as JSON, for CI and other tools"
)
def term_check(
    scripts: tuple[str, ...],
    ignore: tuple[str, ...],
    update: bool,
    shell: str | None,
    as_json: bool,
):
    """Check that recordings made from steps still match what the steps produce.

    Each script's steps are run again, as `record --steps` would, and the
    screen is compared with the committed recording at every marker and at
    the end. Timing isn't compared. Give the .termshow.yml scripts, or the
    .termshow recordings they belong to.

    Text that changes from run to run, such as a version number or a
    temporary path, can be left out with --ignore or the script's
    `check.ignore` list.

    Exits with status 1 if any recording has drifted or a step failed. With
    --update, recordings that have drifted are recorded again instead.

    With --json, the results are printed as one JSON object instead, with
    the same exit status. Progress still goes to stderr.

    Examples:
      great-docs termshow check docs/assets/*.termshow.yml
      great-docs termshow check docs/assets/install.termshow --ignore 'v\\d+\\.\\d+'
      great-docs termshow check docs/assets/*.termshow.yml --json > drift.json
    """
    import json
    import re

    from .._term_player.check import CheckError, check_script
    from .._term_player.importer import _write_termshow
    from .._term_player.steps import StepsError

    for pattern in ignore:
        try:
            re.compile(pattern)
        except re.error as e:
            raise click.BadParameter(
                f"{pattern!r} isn't a valid regular expression ({e})", param_hint="--ignore"
            ) from None

    results = []
    for script in scripts:
        script_path = Path(script)
        if script_path.name.endswith(".termshow"):
            script_path = script_path.with_name(script_path.name + ".yml")
        click.echo(f"Checking {script_path}", err=True)
        entry = {"script": script_path.as_posix(), "recording": None}
        try:
            result = check_script(script_path, ignore=ignore, shell=shell)
        except (CheckError, StepsError) as e:
            entry |= {"status": "failed", "error": str(e)}
            if isinstance(e, StepsError) and e.screen:
                entry["screen"] = e.screen
            results.append(entry)
            if not as_json:
                _echo_check_failure(entry)
            continue

        entry |= {
            "recording": result.recording_path.as_posix(),
            "status": "drifted" if result.drifted else "up_to_date",
            "compared": result.snapshots,
            "differences": [{"at": d.where, "diff": d.lines} for d in result.differences],
        }
        if result.drifted and update:
            _write_termshow(result.recording, result.recording_path)
            entry["status"] = "updated"
        results.append(entry)
        if not as_json:
            _echo_check_result(entry)

    counts = {
        status: sum(r["status"] == status for r in results)
        for status in ("up_to_date", "drifted", "updated", "failed")
    }
    if as_json:
        click.echo(json.dumps({"version": 1, "summary": counts, "results": results}, indent=2))
    elif len(scripts) > 1:
        changed = counts["drifted"] + counts["updated"]
        click.echo(
            f"\n{counts['up_to_date']} of {len(scripts)} up to date"
            + (f", {changed} {'updated' if update else 'drifted'}" if changed else "")
            + (f", {counts['failed']} couldn't be checked" if counts["failed"] else "")
        )
    if counts["failed"] or counts["drifted"]:
        raise SystemExit(1)


def _echo_check_failure(entry: dict) -> None:
    click.echo(f"✗ {entry['script']}: {entry['error']}")
    if entry.get("screen"):
        click.echo("\nThe screen at the time:")
        for line in entry["screen"].splitlines():
            click.echo(f"  │ {line}")


def _echo_check_result(entry: dict) -> None:
    recording = entry["recording"]
    if entry["status"] == "up_to_date":
        screens = f"{entry['compared']} screen{'' if entry['compared'] == 1 else 's'}"
        click.echo(f"✓ {recording} is up to date ({screens} compared)")
        return
    click.echo(f"✗ {recording} has drifted:\n")
    for difference in entry["differences"]:
        for line in difference["diff"]:
            color = {"+": "green", "-": "red", "@": "cyan"}.get(line[:1])
            if line.startswith(("+++", "---")):
                color = None
            click.secho(f"  {line}", fg=color)
        click.echo()
    if entry["status"] == "updated":
        click.echo(f"↻ Recorded {recording} again")


@click.command("assets")
@click.argument("dest", type=click.Path(file_okay=False))
def term_assets(dest: str) -> None:
    """Copy the web player into a directory, for pages built without Quarto.

    Writes termshow.js, termshow.css, and the fonts the stylesheet uses, then
    prints the HTML that loads them. Point a <termshow-player> element's src
    at a `termshow render` output directory to embed a recording.

    Examples:
      great-docs termshow assets site/player
    """
    from .._term_player.web import copy_player, player_snippet

    files = copy_player(dest)
    click.echo(f"✓ Copied {len(files)} player files to {dest}/")
    click.echo("\nAdd this to a page, with src pointing at a rendered recording:\n")
    click.echo(player_snippet(Path(dest).as_posix()))


@click.command("edit")
@click.argument("source", type=click.Path(exists=True))
@click.option("--port", type=int, default=8765, help="Local server port")
@click.option("--no-browser", is_flag=True, help="Don't auto-open browser")
def term_edit(source: str, port: int, no_browser: bool) -> None:
    """Open the Termshow Editor for a .termshow recording.

    Launches a browser-based timeline editor for adding chapters,
    annotations, and cuts. Changes are saved back to the .termshow.yml
    script file.

    Examples:
      great-docs termshow edit demos/my-demo.termshow
      great-docs termshow edit demos/install.termshow --port 9000
    """
    from .._term_player.editor import serve_editor

    serve_editor(source, port=port, no_browser=no_browser)


termshow.add_command(term_record)
termshow.add_command(term_render)
termshow.add_command(term_play)
termshow.add_command(term_export)
termshow.add_command(term_snap)
termshow.add_command(term_transcript)
termshow.add_command(term_validate)
termshow.add_command(term_check)
termshow.add_command(term_assets)
termshow.add_command(term_import_cast)
termshow.add_command(term_import_tape)
termshow.add_command(term_edit)
