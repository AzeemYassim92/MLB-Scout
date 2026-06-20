from __future__ import annotations

from datetime import date, timedelta

from mlbpicker.analytics import (
    build_pitcher_matchup_analytics,
    build_projection_context,
    expected_innings,
    expected_pitch_count,
)
from mlbpicker.model import StrikeoutProjector
from mlbpicker.providers.base import ProviderError
from mlbpicker.providers.mlb_stats_provider import MlbStatsProvider
from mlbpicker.providers.odds_provider import OddsApiProvider
from mlbpicker.schemas import GamePitchingOdds, PitcherMatchupAnalytics, PitcherPropLine, ScheduledGame, StrikeoutProjection


STAT_DESCRIPTIONS = {
    "Pitcher": "Probable starter listed by MLB Stats API for the selected game date.",
    "Throws": "Pitcher's throwing hand from MLB player metadata.",
    "Reliability": "0-100 input confidence score based on available pitcher, opponent, recent-game, pitch-level, and hitter-profile data.",
    "Projected Ks": "Baseline strikeout projection from our current model using live pitcher and opponent inputs.",
    "Pitcher K%": "Pitcher's strikeouts divided by batters faced, using MLB advanced pitching stats when available.",
    "K/9": "Pitcher's strikeouts per nine innings.",
    "BB%": "Pitcher's walks divided by batters faced.",
    "Whiff%": "Pitcher's swing-and-miss rate per swing from MLB advanced pitching stats.",
    "Recent SwStr%": "Recent swinging strikes divided by total pitches from recent MLB game pitch feeds.",
    "Recent CSW": "Called strikes plus whiffs from recent MLB pitch feeds, shown as count and rate.",
    "Strike%": "Pitcher's total strikes divided by total pitches.",
    "Exp pitches": "Expected pitch count estimated from recent starts, falling back to season pitches per start.",
    "Exp innings": "Expected innings estimated from recent starts, falling back to season innings per start.",
    "Opponent K%": "Opponent team strikeouts divided by plate appearances.",
    "Opponent whiff%": "Opponent team swing-and-miss rate per swing.",
    "Lineup strength": "Derived 0-100 danger score using opponent OPS and strikeout rate. Higher means tougher offense.",
    "K friendliness": "Derived 0-100 strikeout opportunity score using opponent K rate and OPS. Higher favors pitcher strikeouts.",
    "Opponent IL/40-man": "Count of non-active or injury-status players returned from the opponent's 40-man roster.",
    "Source": "Probable pitcher source currently used by the app.",
    "BetMGM K line": "BetMGM pitcher strikeout over/under from The Odds API, when available.",
    "BetMGM Over": "American odds for the over side of the BetMGM pitcher strikeout prop.",
    "BetMGM Under": "American odds for the under side of the BetMGM pitcher strikeout prop.",
    "Model edge": "Our projected strikeouts minus the BetMGM strikeout line. Positive leans over, negative leans under.",
    "Odds source": "Pitching prop source. We query The Odds API for BetMGM only and pitcher_strikeouts only.",
    "Odds quota": "The Odds API quota headers: remaining requests and cost of the last odds request.",
    "Odds status": "Whether the BetMGM pitcher strikeout market loaded, is missing, or needs API key configuration.",
    "Name": "Active roster hitter name. This is not yet a confirmed batting order.",
    "Pos/Bat": "Player position and batting side.",
    "PA": "Season plate appearances.",
    "K%": "Strikeouts divided by plate appearances.",
    "OPS": "On-base plus slugging.",
    "Whiff%": "Swing-and-miss rate per swing.",
}


def main(page) -> None:
    import flet as ft

    page.title = "MLB Strikeout Picker"
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_min_width = 1160
    page.window_min_height = 820

    provider = MlbStatsProvider()
    try:
        odds_provider: OddsApiProvider | None = OddsApiProvider()
        odds_provider_note = None
    except ProviderError as exc:
        odds_provider = None
        odds_provider_note = str(exc)
    projector = StrikeoutProjector()
    games_by_key: dict[str, ScheduledGame] = {}
    current_analytics: dict[str, PitcherMatchupAnalytics] = {}
    current_projections: dict[str, StrikeoutProjection | None] = {}
    current_odds: GamePitchingOdds | None = None

    status = ft.Text("Ready")
    matchup_date = ft.TextField(
        label="Matchup date",
        value=date.today().isoformat(),
        width=180,
    )
    matchup_dropdown = ft.Dropdown(label="Matchup", options=[], width=560)
    matchup_dropdown.on_select = lambda event: select_matchup(event.control.value)
    detail_dropdown = ft.Dropdown(
        label="Detail",
        options=[
            ft.dropdown.Option(key="away", text="Away pitcher vs home bats"),
            ft.dropdown.Option(key="home", text="Home pitcher vs away bats"),
        ],
        value="away",
        width=320,
    )
    detail_dropdown.on_select = lambda event: render_detail(event.control.value)

    game_detail = ft.Text("Load a date, then choose a matchup.")
    away_box = ft.Container(expand=True)
    home_box = ft.Container(expand=True)
    detail_box = ft.Container(expand=True)

    def set_date(target_date: date) -> None:
        matchup_date.value = target_date.isoformat()
        load_matchups()

    def load_matchups(_event=None) -> None:
        nonlocal games_by_key
        status.value = "Loading matchups..."
        page.update()
        try:
            selected_date = date.fromisoformat(matchup_date.value)
            games = provider.fetch_schedule(selected_date)
        except (ProviderError, ValueError) as exc:
            status.value = str(exc)
            page.update()
            return

        games_by_key = {str(game.game_pk): game for game in games}
        matchup_dropdown.options = [
            ft.dropdown.Option(
                key=str(game.game_pk),
                text=f"{game.away_team} at {game.home_team}",
            )
            for game in games
        ]
        matchup_dropdown.value = str(games[0].game_pk) if games else None
        status.value = f"Loaded {len(games)} matchup(s)"

        if games:
            select_matchup(str(games[0].game_pk), update=False)
        else:
            game_detail.value = "No games found for that date."
            away_box.content = _empty_box(ft, "Away Team")
            home_box.content = _empty_box(ft, "Home Team")
            detail_box.content = ft.Text("No detail available.")
        page.update()

    def select_matchup(game_key: str | None, update: bool = True) -> None:
        nonlocal current_odds
        if not game_key or game_key not in games_by_key:
            return

        game = games_by_key[game_key]
        status.value = "Loading pitcher, opponent, recent pitch, injury, and BetMGM data..."
        page.update()

        try:
            away_analytics = build_pitcher_matchup_analytics(provider, game, "away")
            home_analytics = build_pitcher_matchup_analytics(provider, game, "home")
        except ProviderError as exc:
            status.value = str(exc)
            page.update()
            return

        current_analytics["away"] = away_analytics
        current_analytics["home"] = home_analytics
        current_projections["away"] = _project(projector, game, away_analytics)
        current_projections["home"] = _project(projector, game, home_analytics)
        current_odds = _load_pitching_odds(odds_provider, game, odds_provider_note)

        game_detail.value = f"{game.venue} | {game.status} | {game.start_time_utc or 'Start time TBD'}"
        away_box.content = _analytics_box(ft, "Away Team", away_analytics, current_projections["away"], current_odds)
        home_box.content = _analytics_box(ft, "Home Team", home_analytics, current_projections["home"], current_odds)
        render_detail(detail_dropdown.value or "away", update=False)
        status.value = f"Selected {game.away_team} at {game.home_team}"
        if update:
            page.update()

    def render_detail(side: str | None, update: bool = True) -> None:
        analytics = current_analytics.get(side or "away")
        if not analytics:
            detail_box.content = ft.Text("Choose a matchup to load hitter detail.")
        else:
            detail_box.content = _detail_panel(ft, analytics)
        if update:
            page.update()

    page.add(
        ft.Column(
            [
                ft.Text("MLB Strikeout Picker", size=24, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        matchup_date,
                        ft.Button(
                            "Today",
                            icon=ft.Icons.TODAY,
                            on_click=lambda _event: set_date(date.today()),
                        ),
                        ft.Button(
                            "Tomorrow",
                            icon=ft.Icons.NEXT_PLAN,
                            on_click=lambda _event: set_date(date.today() + timedelta(days=1)),
                        ),
                        ft.Button("Load", icon=ft.Icons.CALENDAR_MONTH, on_click=load_matchups),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                matchup_dropdown,
                game_detail,
                ft.Row([away_box, home_box], spacing=16, expand=False),
                ft.Row([detail_dropdown], alignment=ft.MainAxisAlignment.START),
                detail_box,
                status,
            ],
            spacing=14,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
    )

    load_matchups()


def _project(projector: StrikeoutProjector, game: ScheduledGame, analytics: PitcherMatchupAnalytics):
    context = build_projection_context(game.game_date, game.venue, analytics)
    if not context:
        return None
    return projector.project(context)


def _load_pitching_odds(
    odds_provider: OddsApiProvider | None,
    game: ScheduledGame,
    provider_note: str | None,
) -> GamePitchingOdds:
    if not odds_provider:
        return GamePitchingOdds(
            event_id=None,
            home_team=None,
            away_team=None,
            note=provider_note or "BetMGM pitching prop provider is not configured.",
        )
    try:
        return odds_provider.fetch_pitcher_strikeout_lines(game)
    except ProviderError as exc:
        return GamePitchingOdds(
            event_id=None,
            home_team=None,
            away_team=None,
            note=str(exc),
        )


def _empty_box(ft, title: str):
    return ft.Container(
        bgcolor=ft.Colors.WHITE,
        border_radius=6,
        padding=16,
        content=ft.Column([ft.Text(title, size=20, weight=ft.FontWeight.BOLD), ft.Text("No matchup selected.")]),
    )


def _analytics_box(
    ft,
    label: str,
    analytics: PitcherMatchupAnalytics,
    projection: StrikeoutProjection | None,
    pitching_odds: GamePitchingOdds | None,
):
    stats = analytics.pitcher_stats
    opponent = analytics.opponent_stats
    metrics = analytics.pitch_metrics
    reliability = analytics.reliability
    prop_line = _prop_line_for_pitcher(pitching_odds, analytics.pitcher_name)

    stat_rows = [
        _stat_row(ft, "Pitcher", analytics.pitcher_name or "TBD"),
        _stat_row(ft, "Source", "MLB Stats API probablePitcher"),
        _stat_row(ft, "Odds source", "The Odds API / BetMGM"),
        _stat_row(ft, "Odds status", _odds_status(pitching_odds, analytics.pitcher_name, prop_line)),
        _stat_row(ft, "Odds quota", _quota_text(pitching_odds)),
        _stat_row(ft, "BetMGM K line", _line_text(prop_line)),
        _stat_row(ft, "BetMGM Over", _display(prop_line.over_price if prop_line else None)),
        _stat_row(ft, "BetMGM Under", _display(prop_line.under_price if prop_line else None)),
        _stat_row(ft, "Model edge", _edge_text(projection, prop_line)),
        _stat_row(ft, "Throws", stats.pitch_hand if stats else "-"),
        _stat_row(ft, "Reliability", _reliability_text(reliability)),
        _stat_row(ft, "Projected Ks", projection.projected_strikeouts if projection else "-"),
        _stat_row(ft, "Pitcher K%", _pct(stats.strikeout_rate if stats else None)),
        _stat_row(ft, "K/9", _display(stats.strikeouts_per_9 if stats else None)),
        _stat_row(ft, "BB%", _pct(stats.walk_rate if stats else None)),
        _stat_row(ft, "Whiff%", _pct(stats.whiff_rate if stats else None)),
        _stat_row(ft, "Recent SwStr%", _pct(metrics.swinging_strike_rate if metrics else None)),
        _stat_row(ft, "Recent CSW", _csw_text(metrics)),
        _stat_row(ft, "Strike%", _pct(stats.strike_percentage if stats else None)),
        _stat_row(ft, "Exp pitches", _display(expected_pitch_count(analytics))),
        _stat_row(ft, "Exp innings", _display(expected_innings(analytics))),
        _stat_row(ft, "Opponent K%", _pct(opponent.strikeout_rate if opponent else None)),
        _stat_row(ft, "Opponent whiff%", _pct(opponent.whiff_rate if opponent else None)),
        _stat_row(ft, "Lineup strength", _display(opponent.lineup_strength_score if opponent else None)),
        _stat_row(ft, "K friendliness", _display(opponent.strikeout_friendliness_score if opponent else None)),
        _stat_row(ft, "Opponent IL/40-man", len(analytics.opponent_injuries)),
    ]

    notes = []
    if reliability and reliability.missing:
        notes = reliability.missing[:3]
    if projection and projection.notes:
        notes.extend(projection.notes[:2])
    odds_note = _odds_note(pitching_odds, analytics.pitcher_name, prop_line)
    if odds_note:
        notes.append(odds_note)

    return ft.Container(
        bgcolor=ft.Colors.WHITE,
        border_radius=6,
        padding=16,
        content=ft.Column(
            [
                ft.Text(label.upper(), size=12, color=ft.Colors.GREY_700),
                ft.Text(
                    f"{analytics.team_name} vs {analytics.opponent_team_name}",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(height=18),
                *stat_rows,
                ft.Divider(height=18),
                ft.Text("Notes", size=14, weight=ft.FontWeight.BOLD),
                *_note_controls(ft, notes),
            ],
            spacing=7,
        ),
    )


def _detail_panel(ft, analytics: PitcherMatchupAnalytics):
    hitter_rows = [
        _hitter_row(ft, "Name", "Pos/Bat", "PA", "K%", "OPS", "Whiff%", header=True),
    ]
    for hitter in analytics.opponent_hitters[:12]:
        hitter_rows.append(
            _hitter_row(
                ft,
                hitter.name,
                f"{hitter.position}/{hitter.bat_side or '-'}",
                _display(hitter.plate_appearances),
                _pct(hitter.strikeout_rate),
                _display(hitter.ops),
                _pct(hitter.whiff_rate),
            )
        )

    injury_controls = []
    if analytics.opponent_injuries:
        for injury in analytics.opponent_injuries[:8]:
            note = f" - {injury.note}" if injury.note else ""
            injury_controls.append(ft.Text(f"{injury.name} ({injury.position}): {injury.status}{note}"))
    else:
        injury_controls.append(ft.Text("No 40-man injury statuses returned for this opponent."))

    return ft.Container(
        bgcolor=ft.Colors.WHITE,
        border_radius=6,
        padding=16,
        content=ft.Column(
            [
                ft.Text(
                    f"{analytics.pitcher_name or 'TBD'} vs {analytics.opponent_team_name} active hitters",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Active roster sample, not a confirmed lineup. Handedness split and batter-vs-pitcher history are pending.",
                    color=ft.Colors.GREY_700,
                ),
                ft.Divider(height=18),
                *hitter_rows,
                ft.Divider(height=18),
                ft.Text("Opponent Injuries / Non-Active 40-Man", size=14, weight=ft.FontWeight.BOLD),
                *injury_controls,
            ],
            spacing=6,
        ),
    )


def _hitter_row(ft, name: str, pos: str, pa: object, k_rate: object, ops: object, whiff: object, header: bool = False):
    weight = ft.FontWeight.BOLD if header else None
    color = ft.Colors.GREY_700 if header else None
    name_tooltip = STAT_DESCRIPTIONS.get(str(name))
    pos_tooltip = STAT_DESCRIPTIONS.get(str(pos))
    return ft.Row(
        [
            ft.Text(str(name), width=260, weight=weight, color=color, tooltip=name_tooltip),
            ft.Text(str(pos), width=80, weight=weight, color=color, tooltip=pos_tooltip),
            ft.Text(str(pa), width=70, weight=weight, color=color, tooltip=STAT_DESCRIPTIONS.get("PA")),
            ft.Text(str(k_rate), width=80, weight=weight, color=color, tooltip=STAT_DESCRIPTIONS.get("K%")),
            ft.Text(str(ops), width=80, weight=weight, color=color, tooltip=STAT_DESCRIPTIONS.get("OPS")),
            ft.Text(str(whiff), width=90, weight=weight, color=color, tooltip=STAT_DESCRIPTIONS.get("Whiff%")),
        ],
        spacing=8,
    )


def _stat_row(ft, label: str, value: object):
    tooltip = STAT_DESCRIPTIONS.get(label)
    return ft.Row(
        [
            ft.Text(label, color=ft.Colors.GREY_700, expand=True, tooltip=tooltip),
            ft.Text(str(value), weight=ft.FontWeight.BOLD, tooltip=tooltip),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


def _note_controls(ft, notes: list[str]):
    if not notes:
        return [ft.Text("All core live inputs are available.", color=ft.Colors.GREY_700)]
    return [ft.Text(note, color=ft.Colors.GREY_700) for note in notes]


def _prop_line_for_pitcher(odds: GamePitchingOdds | None, pitcher_name: str | None) -> PitcherPropLine | None:
    if not odds or not pitcher_name:
        return None
    pitcher_key = _name_key(pitcher_name)
    for line in odds.lines:
        if _name_key(line.player_name) == pitcher_key:
            return line
    return None


def _odds_note(
    odds: GamePitchingOdds | None,
    pitcher_name: str | None,
    prop_line: PitcherPropLine | None,
) -> str | None:
    if not odds:
        return "BetMGM pitching props were not requested."
    if odds.note:
        return odds.note
    if pitcher_name and not prop_line:
        available = ", ".join(line.player_name for line in odds.lines[:4])
        if available:
            return f"No BetMGM pitcher K line matched {pitcher_name}. Available lines: {available}."
        return f"No BetMGM pitcher K line matched {pitcher_name}."
    return None


def _odds_status(
    odds: GamePitchingOdds | None,
    pitcher_name: str | None,
    prop_line: PitcherPropLine | None,
) -> str:
    if not odds:
        return "Not requested"
    if odds.note:
        if "THE_ODDS_API_KEY" in odds.note:
            return "Missing API key"
        if "No matching" in odds.note:
            return "No event match"
        if "not available" in odds.note:
            return "Market unavailable"
        return "Error"
    if pitcher_name and not prop_line:
        return "No pitcher match"
    if prop_line:
        return "Loaded"
    return "No lines"


def _line_text(prop_line: PitcherPropLine | None) -> str:
    if not prop_line or prop_line.line is None:
        return "-"
    return f"{_display(prop_line.line)} Ks"


def _quota_text(odds: GamePitchingOdds | None) -> str:
    quota = odds.quota if odds else None
    if not quota:
        return "-"
    remaining = _display(quota.requests_remaining)
    last = _display(quota.requests_last)
    return f"{remaining} left, last {last}"


def _edge_text(projection: StrikeoutProjection | None, prop_line: PitcherPropLine | None) -> str:
    if not projection or not prop_line or prop_line.line is None:
        return "-"
    edge = projection.projected_strikeouts - prop_line.line
    lean = "Over" if edge > 0 else "Under" if edge < 0 else "Push"
    return f"{edge:+.1f} Ks ({lean})"


def _name_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _reliability_text(reliability) -> str:
    if not reliability:
        return "-"
    return f"{reliability.score}/100 {reliability.label}"


def _csw_text(metrics) -> str:
    if not metrics or metrics.total_pitches == 0:
        return "-"
    return f"{metrics.called_strikes_plus_whiffs}/{metrics.total_pitches} ({_pct(metrics.csw_rate)})"


def _pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def _display(value: object) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


if __name__ == "__main__":
    import flet as ft

    ft.run(main)
