import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'master_metrics.dart';
import 'trade.dart';
import 'trading_master.dart' show masterSections;

const masterMint = Color(0xff86dfb4),
    masterRed = Color(0xffed7e86),
    masterMuted = Color(0xff8d98aa),
    masterBorder = Color(0xff293242),
    masterPanel = Color(0xff171f2d);
String masterWon(num n) =>
    '${n < 0 ? '−' : ''}${n.abs().round().toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}원';
String masterPct(num n) => '${n > 0 ? '+' : ''}${n.toStringAsFixed(2)}%';
Color masterSign(num n) => n >= 0 ? masterMint : masterRed;
Widget muted(String s, {double size = 13}) => Text(
  s,
  style: TextStyle(color: masterMuted, fontSize: size, height: 1.65),
);

class MasterPanel extends StatelessWidget {
  final String title;
  final String? caption;
  final Widget child;
  final Widget? action;
  const MasterPanel({
    super.key,
    required this.title,
    required this.child,
    this.caption,
    this.action,
  });
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 22),
    decoration: BoxDecoration(
      color: masterPanel,
      border: Border.all(color: masterBorder),
      borderRadius: BorderRadius.circular(9),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(22, 22, 22, 16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (caption != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 7),
                        child: muted(caption!, size: 12),
                      ),
                  ],
                ),
              ),
              ?action,
            ],
          ),
        ),
        Material(color: Colors.transparent, child: child),
      ],
    ),
  );
}

class MasterCard extends StatelessWidget {
  final String label, value, caption;
  final IconData? icon;
  final Color? color;
  const MasterCard({
    super.key,
    required this.label,
    required this.value,
    this.caption = '',
    this.icon,
    this.color,
  });
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: masterPanel,
      border: Border.all(color: masterBorder),
      borderRadius: BorderRadius.circular(9),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: muted(label, size: 14)),
            if (icon != null) Icon(icon, size: 18, color: masterMuted),
          ],
        ),
        const SizedBox(height: 18),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ),
        const SizedBox(height: 10),
        muted(caption, size: 12),
      ],
    ),
  );
}

Widget cardGrid(List<Widget> cards) => LayoutBuilder(
  builder: (context, c) {
    final count = c.maxWidth < 660 ? 2 : math.min(4, cards.length);
    final width = (c.maxWidth - 16 * (count - 1)) / count;
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: Wrap(
        spacing: 16,
        runSpacing: 16,
        children: [
          for (final card in cards) SizedBox(width: width, child: card),
        ],
      ),
    );
  },
);
Widget pair(Widget a, Widget b, {double left = 1.45}) => LayoutBuilder(
  builder: (context, c) => c.maxWidth < 750
      ? Column(children: [a, b])
      : Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(flex: (left * 100).round(), child: a),
            const SizedBox(width: 22),
            Expanded(flex: 100, child: b),
          ],
        ),
);

class ReferenceMaster extends StatelessWidget {
  final List<Trade> trades;
  final int section, days;
  final bool demo, loading, connected;
  final String? error;
  final String query;
  final ValueChanged<int> onSection, onDays;
  final ValueChanged<String> onSearch;
  final VoidCallback onNew, onImport, onExport, onRefresh, onSettings, onReal;
  final ValueChanged<Trade> onJournal, onEdit;
  final Widget? journal, positionView, openPositions;
  const ReferenceMaster({
    super.key,
    required this.trades,
    required this.section,
    required this.days,
    required this.demo,
    required this.loading,
    required this.connected,
    this.error,
    required this.query,
    required this.onSection,
    required this.onDays,
    required this.onSearch,
    required this.onNew,
    required this.onImport,
    required this.onExport,
    required this.onRefresh,
    required this.onSettings,
    required this.onReal,
    required this.onJournal,
    required this.onEdit,
    this.journal,
    this.positionView,
    this.openPositions,
  });
  static const icons = [
    Icons.dashboard_outlined,
    Icons.calendar_month_outlined,
    Icons.date_range_outlined,
    Icons.assignment_outlined,
    Icons.balance_outlined,
    Icons.track_changes_outlined,
    Icons.bar_chart_outlined,
    Icons.shield_outlined,
  ];
  Widget toolbar(bool mobile) {
    final period = Container(
      height: 38,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        border: Border.all(color: masterBorder),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.calendar_month_outlined,
            size: 16,
            color: masterMuted,
          ),
          const SizedBox(width: 9),
          DropdownButton<int>(
            value: days,
            isDense: true,
            underline: const SizedBox(),
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xffb8c2d2),
              fontFamily: 'DMSans',
              fontFamilyFallback: ['NotoSansKR'],
            ),
            items: const [
              DropdownMenuItem(value: 0, child: Text('전체 기간')),
              DropdownMenuItem(value: 30, child: Text('최근 1개월')),
              DropdownMenuItem(value: 90, child: Text('최근 3개월')),
              DropdownMenuItem(value: 180, child: Text('최근 6개월')),
              DropdownMenuItem(value: 365, child: Text('최근 1년')),
            ],
            onChanged: (v) => onDays(v!),
          ),
        ],
      ),
    );
    final actions = [
      OutlinedButton.icon(
        onPressed: onImport,
        icon: const Icon(Icons.add, size: 15),
        label: const Text('엑셀 가져오기'),
      ),
      muted('${trades.length}건의 거래', size: 12),
      OutlinedButton.icon(
        onPressed: onExport,
        icon: const Icon(Icons.download_outlined, size: 15),
        label: const Text('내보내기'),
      ),
    ];
    final range = trades.isEmpty
        ? '거래 기록 없음'
        : '${MasterMetrics(trades).ordered.first.exit} — ${MasterMetrics(trades).ordered.last.exit}';
    return LayoutBuilder(
      builder: (context, c) => c.maxWidth < 800
          ? Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [period, ...actions],
            )
          : Row(
              children: [
                period,
                const SizedBox(width: 16),
                Expanded(child: muted(range, size: 12)),
                for (int i = 0; i < actions.length; i++) ...[
                  if (i > 0) const SizedBox(width: 16),
                  actions[i],
                ],
              ],
            ),
    );
  }

  Widget sidebar(BuildContext context, {bool drawer = false}) => Container(
    width: 240,
    color: const Color(0xff121a27),
    child: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 32, 20, 20),
        children: [
          Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(7),
                child: Image.asset(
                  'assets/branding/tm-icon.png',
                  width: 32,
                  height: 32,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text.rich(
                      TextSpan(
                        text: 'Trading',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 19,
                        ),
                        children: [
                          TextSpan(
                            text: 'Master',
                            style: TextStyle(fontWeight: FontWeight.normal),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 7),
                    muted('YOUR TRADING JOURNAL', size: 9),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 38),
          muted('WORKSPACE', size: 11),
          const SizedBox(height: 12),
          for (int i = 0; i < masterSections.length; i++) ...[
            if (i == 4)
              Padding(
                padding: const EdgeInsets.only(top: 22, bottom: 12),
                child: muted('분석 도구', size: 12),
              ),
            Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Material(
                color: section == i
                    ? const Color(0xff243c37)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(7),
                child: InkWell(
                  key: ValueKey('master-nav-$i'),
                  borderRadius: BorderRadius.circular(7),
                  onTap: () {
                    if (drawer) Navigator.pop(context);
                    onSection(i);
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 13,
                    ),
                    child: Row(
                      children: [
                        Icon(
                          icons[i],
                          size: 19,
                          color: section == i ? masterMint : masterMuted,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            masterSections[i],
                            style: TextStyle(
                              fontSize: 14,
                              color: section == i ? masterMint : masterMuted,
                              fontWeight: section == i
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 30),
          Container(
            padding: const EdgeInsets.all(15),
            decoration: BoxDecoration(
              color: const Color(0xff1b2932),
              border: Border.all(color: masterBorder),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.verified_user_outlined,
                  color: masterMint,
                  size: 22,
                ),
                const SizedBox(height: 13),
                const Text(
                  '기록이 만드는 나의 엣지',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 6),
                muted('결과보다 과정을 돌아보세요.', size: 12),
              ],
            ),
          ),
          const SizedBox(height: 18),
          TextButton.icon(
            onPressed: () {
              if (drawer) Navigator.pop(context);
              onSettings();
            },
            icon: const Icon(Icons.settings_outlined, size: 18),
            label: const Text('설정'),
          ),
          const Divider(height: 36),
          Row(
            children: [
              avatar(),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '나의 트레이딩 저널',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    muted('개인 워크스페이스', size: 11),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, c) {
      final mobile = c.maxWidth < 760;
      return Scaffold(
        drawer: mobile
            ? Drawer(width: 240, child: sidebar(context, drawer: true))
            : null,
        body: Row(
          children: [
            if (!mobile)
              SizedBox(
                width: c.maxWidth < 1200 ? 210 : 240,
                child: sidebar(context),
              ),
            Expanded(
              child: Column(
                children: [
                  Container(
                    height: mobile ? 60 : 74,
                    decoration: const BoxDecoration(
                      border: Border(bottom: BorderSide(color: masterBorder)),
                    ),
                    padding: EdgeInsets.symmetric(
                      horizontal: mobile
                          ? 18
                          : c.maxWidth < 1200
                          ? 24
                          : 36,
                    ),
                    child: Row(
                      children: [
                        if (mobile)
                          Builder(
                            builder: (c) => IconButton(
                              tooltip: '메뉴 열기',
                              onPressed: () => Scaffold.of(c).openDrawer(),
                              icon: const Icon(Icons.menu),
                            ),
                          ),
                        if (!mobile) muted('워크스페이스', size: 13),
                        if (!mobile)
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 12),
                            child: Icon(
                              Icons.chevron_right,
                              size: 14,
                              color: masterMuted,
                            ),
                          ),
                        Expanded(
                          child: Text(
                            journal == null ? masterSections[section] : '매매일지',
                            style: const TextStyle(
                              color: Color(0xffb8c2d2),
                              fontSize: 13,
                            ),
                          ),
                        ),
                        if (!mobile) ...[
                          const Icon(
                            Icons.verified_user_outlined,
                            size: 14,
                            color: masterMuted,
                          ),
                          const SizedBox(width: 7),
                          muted('개인 저널', size: 12),
                          const SizedBox(width: 14),
                        ],
                        IconButton(
                          tooltip: '설정',
                          onPressed: onSettings,
                          icon: const Icon(
                            Icons.settings_outlined,
                            size: 19,
                            color: masterMuted,
                          ),
                        ),
                        const SizedBox(width: 12),
                        avatar(),
                      ],
                    ),
                  ),
                  Expanded(
                    child: RefreshIndicator(
                      onRefresh: () async => onRefresh(),
                      child: ListView(
                        key: ValueKey(
                          'master-body-$section-${journal != null}',
                        ),
                        padding: EdgeInsets.fromLTRB(
                          mobile
                              ? 18
                              : c.maxWidth < 1200
                              ? 24
                              : 36,
                          mobile ? 25 : 37,
                          mobile
                              ? 18
                              : c.maxWidth < 1200
                              ? 24
                              : 36,
                          24,
                        ),
                        children: [
                          if (journal != null)
                            journal!
                          else ...[
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        section == 0
                                            ? 'PERFORMANCE OVERVIEW'
                                            : 'TRADING JOURNAL',
                                        style: const TextStyle(
                                          fontSize: 10,
                                          letterSpacing: 1.8,
                                          color: masterMint,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      const SizedBox(height: 10),
                                      Text(
                                        section == 0
                                            ? '나의 트레이딩, 한눈에.'
                                            : masterSections[section],
                                        style: TextStyle(
                                          fontSize: mobile ? 24 : 30,
                                          fontWeight: FontWeight.w600,
                                          letterSpacing: -.6,
                                        ),
                                      ),
                                      const SizedBox(height: 10),
                                      muted(
                                        section == 0
                                            ? '꾸준한 기록으로 성과를 확인하고, 나만의 매매 패턴을 발견하세요.'
                                            : section == 7
                                            ? '최초 위험은 고정하고, 차수별 CR과 E로 수익 반납 위험을 확인하세요.'
                                            : section == 5
                                            ? '계좌별 고정 R 기준으로 청산 거래의 성과를 확인하세요.'
                                            : '매매 기록을 바탕으로 거래 성과를 살펴보세요.',
                                        size: mobile ? 12 : 14,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                if (![5, 7].contains(section))
                                  FilledButton.icon(
                                    onPressed: onNew,
                                    icon: const Icon(Icons.add, size: 18),
                                    label: const Text('거래 등록'),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 27),
                            if (![5, 7].contains(section)) toolbar(mobile),
                            const SizedBox(height: 20),
                            if (demo && ![5, 7].contains(section))
                              Container(
                                margin: const EdgeInsets.only(bottom: 20),
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: const Color(0xff20372f),
                                  border: Border.all(
                                    color: const Color(0xff36534e),
                                  ),
                                  borderRadius: BorderRadius.circular(7),
                                ),
                                child: Wrap(
                                  spacing: 14,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    const Icon(
                                      Icons.info_outline,
                                      size: 16,
                                      color: masterMint,
                                    ),
                                    const Text(
                                      '샘플 데이터 미리보기',
                                      style: TextStyle(
                                        color: masterMint,
                                        fontWeight: FontWeight.w600,
                                        fontSize: 12,
                                      ),
                                    ),
                                    if (!mobile)
                                      muted('실제 매매 성과가 아닙니다.', size: 12),
                                    TextButton(
                                      onPressed: onReal,
                                      child: const Text('내 기록으로 전환 ›'),
                                    ),
                                  ],
                                ),
                              ),
                            if (error != null)
                              Container(
                                margin: const EdgeInsets.only(bottom: 16),
                                padding: const EdgeInsets.all(16),
                                color: const Color(0xff3b252e),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        error!,
                                        style: const TextStyle(
                                          color: masterRed,
                                        ),
                                      ),
                                    ),
                                    TextButton(
                                      onPressed: onRefresh,
                                      child: const Text('다시 시도'),
                                    ),
                                  ],
                                ),
                              ),
                            if (loading && !demo)
                              const LinearProgressIndicator(),
                            if (section == 3 && openPositions != null)
                              openPositions!,
                            if ([5, 7].contains(section) &&
                                positionView != null)
                              positionView!
                            else if (trades.isEmpty && !loading)
                              MasterPanel(
                                title: section == 3
                                    ? '청산 완료 기록이 없습니다'
                                    : '아직 거래 기록이 없습니다',
                                child: Padding(
                                  padding: const EdgeInsets.all(30),
                                  child: Column(
                                    children: [
                                      const Icon(
                                        Icons.assignment_outlined,
                                        size: 32,
                                        color: masterMint,
                                      ),
                                      const SizedBox(height: 18),
                                      muted('첫 거래를 등록하고 나의 매매 패턴을 발견해보세요.'),
                                      const SizedBox(height: 18),
                                      FilledButton.icon(
                                        onPressed: onNew,
                                        icon: const Icon(Icons.add),
                                        label: const Text('첫 거래 등록'),
                                      ),
                                    ],
                                  ),
                                ),
                              )
                            else
                              MasterAnalysis(
                                key: ValueKey(section),
                                trades: trades,
                                section: section,
                                query: query,
                                onSearch: onSearch,
                                onSection: onSection,
                                onJournal: onJournal,
                                onEdit: onEdit,
                                demo: demo,
                              ),
                          ],
                          const SizedBox(height: 20),
                          const Divider(),
                          Row(
                            children: [
                              const Icon(
                                Icons.diamond_outlined,
                                size: 15,
                                color: masterMuted,
                              ),
                              const SizedBox(width: 8),
                              muted('Trading Master', size: 12),
                              if (!mobile) ...[
                                const SizedBox(width: 20),
                                Expanded(
                                  child: muted(
                                    '나의 매매 기록과 행동을 돌아보기 위한 저널입니다.',
                                    size: 12,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    },
  );
}

class MasterDiamond extends StatelessWidget {
  final double size;
  const MasterDiamond({super.key, this.size = 23});
  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: CustomPaint(painter: _DiamondPainter()),
  );
}

class _DiamondPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()
      ..moveTo(size.width / 2, 2)
      ..lineTo(size.width - 2, size.height / 2)
      ..lineTo(size.width / 2, size.height - 2)
      ..lineTo(2, size.height / 2)
      ..close();
    canvas.drawPath(
      path,
      Paint()
        ..color = masterMint
        ..strokeWidth = 1.8
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

Widget avatar() => const CircleAvatar(
  radius: 17,
  backgroundColor: Color(0xff293948),
  child: Text(
    'ME',
    style: TextStyle(
      fontSize: 11,
      color: Color(0xffb7d3c7),
      fontWeight: FontWeight.w700,
    ),
  ),
);
Widget badge(String text, {Color color = masterMuted}) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
  decoration: BoxDecoration(
    color: color.withValues(alpha: .12),
    borderRadius: BorderRadius.circular(4),
  ),
  child: Text(text, style: TextStyle(color: color, fontSize: 11)),
);

class MasterTradeTable extends StatelessWidget {
  final List<Trade> trades;
  final bool compact;
  final ValueChanged<Trade> onJournal, onEdit;
  const MasterTradeTable({
    super.key,
    required this.trades,
    required this.onJournal,
    required this.onEdit,
    this.compact = false,
  });
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    scrollDirection: Axis.horizontal,
    child: DataTable(
      columnSpacing: 22,
      horizontalMargin: 20,
      dataRowMinHeight: 74,
      dataRowMaxHeight: 78,
      headingRowHeight: 42,
      headingTextStyle: const TextStyle(
        color: masterMuted,
        fontSize: 12,
        fontFamily: 'DMSans',
        fontFamilyFallback: ['NotoSansKR'],
      ),
      dataTextStyle: const TextStyle(
        color: Color(0xffc7d1df),
        fontSize: 13,
        fontFamily: 'DMSans',
        fontFamilyFallback: ['NotoSansKR'],
      ),
      dividerThickness: .5,
      columns: [
        const DataColumn(label: Text('종목 / 청산일')),
        if (!compact) ...const [
          DataColumn(label: Text('진입일')),
          DataColumn(label: Text('보유기간')),
          DataColumn(label: Text('매수금액')),
        ],
        ...const [
          DataColumn(label: Text('실현 손익')),
          DataColumn(label: Text('수익률')),
          DataColumn(label: Text('거래 구분')),
          DataColumn(label: Text('매매일지')),
          DataColumn(label: Text('')),
        ],
      ],
      rows: [
        for (final t in trades)
          DataRow(
            onSelectChanged: (_) => onJournal(t),
            cells: [
              DataCell(
                Row(
                  children: [
                    Container(
                      width: 30,
                      height: 32,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: const Color(0xff243346),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(t.ticker.substring(0, 1)),
                    ),
                    const SizedBox(width: 10),
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          t.ticker,
                          style: const TextStyle(
                            color: masterMint,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 7),
                        muted(t.exit, size: 11),
                      ],
                    ),
                  ],
                ),
              ),
              if (!compact) ...[
                DataCell(Text(t.entry.isEmpty ? '—' : t.entry)),
                DataCell(Text('${holding(t) ?? '—'}일')),
                DataCell(Text(masterWon(t.buy))),
              ],
              DataCell(
                Text(
                  '${t.pnl > 0 ? '+' : ''}${masterWon(t.pnl)}',
                  style: TextStyle(color: masterSign(t.pnl)),
                ),
              ),
              DataCell(
                Text(
                  masterPct(t.roi),
                  style: TextStyle(color: masterSign(t.roi)),
                ),
              ),
              DataCell(
                badge(
                  (t.extra['tags'] as List? ?? []).isEmpty ? '정상 거래' : '실수 기록',
                  color: (t.extra['tags'] as List? ?? []).isEmpty
                      ? masterMint
                      : const Color(0xffd7c58d),
                ),
              ),
              DataCell(
                TextButton(
                  onPressed: () => onJournal(t),
                  child: Text(t.memo.trim().isEmpty ? '복기 작성' : '복기 보기'),
                ),
              ),
              DataCell(
                IconButton(
                  tooltip: '${t.ticker} 거래 수정',
                  onPressed: () => onEdit(t),
                  icon: const Icon(
                    Icons.edit_outlined,
                    size: 15,
                    color: masterMuted,
                  ),
                ),
              ),
            ],
          ),
      ],
      showCheckboxColumn: false,
    ),
  );
}

class MasterAnalysis extends StatefulWidget {
  final List<Trade> trades;
  final int section;
  final String query;
  final bool demo;
  final ValueChanged<String> onSearch;
  final ValueChanged<int> onSection;
  final ValueChanged<Trade> onJournal, onEdit;
  const MasterAnalysis({
    super.key,
    required this.trades,
    required this.section,
    required this.query,
    required this.demo,
    required this.onSearch,
    required this.onSection,
    required this.onJournal,
    required this.onEdit,
  });
  @override
  State<MasterAnalysis> createState() => _MasterAnalysisState();
}

class _MasterAnalysisState extends State<MasterAnalysis> {
  String? year;
  final checked = <int>{};
  MasterMetrics get m => MasterMetrics(widget.trades);
  Widget table(List<Trade> rows, {bool compact = false}) => MasterTradeTable(
    trades: rows,
    onJournal: widget.onJournal,
    onEdit: widget.onEdit,
    compact: compact,
  );
  List<ChartPoint> groupedPoints(int length) {
    final values = <String, double>{};
    for (final t in m.ordered) {
      final key = t.exit.substring(0, length);
      values[key] = (values[key] ?? 0) + t.pnl;
    }
    return values.entries.map((e) => ChartPoint(e.key, e.value)).toList();
  }

  List<ChartPoint> get curve {
    double sum = 0;
    return groupedPoints(10)
        .map((p) => ChartPoint(p.label, sum += p.value))
        .toList();
  }

  Widget overview() => Column(
    children: [
      cardGrid([
        MasterCard(
          label: '누적 실현 손익',
          value: '${m.net > 0 ? '+' : ''}${masterWon(m.net)}',
          caption:
              '총 매수금액 ${masterWon(widget.trades.fold<double>(0, (a, t) => a + t.buy))}',
          icon: Icons.account_balance_wallet_outlined,
          color: masterSign(m.net),
        ),
        MasterCard(
          label: '전체 승률',
          value: '${m.winRate.toStringAsFixed(1)}%',
          caption:
              '${m.wins.length}회 수익 · ${m.losses.length}회 손실 · ${m.n - m.wins.length - m.losses.length}회 본전',
          icon: Icons.track_changes_outlined,
        ),
        MasterCard(
          label: 'Profit Factor',
          value: ratio(m.profitFactor),
          caption: '총 수익금 ÷ 총 손실금',
          icon: Icons.monitor_heart_outlined,
        ),
        MasterCard(
          label: '거래당 기대수익률',
          value: masterPct(m.expectancy),
          caption: '평균 손익 ${masterWon(m.n == 0 ? 0 : m.net / m.n)}',
          icon: Icons.trending_up,
          color: masterSign(m.expectancy),
        ),
      ]),
      pair(
        MasterPanel(
          title: '누적 손익',
          caption: '청산일 기준 실현 손익의 흐름',
          action: muted('● 누적 손익', size: 11),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 22,
                  vertical: 8,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${m.net > 0 ? '+' : ''}${masterWon(m.net)}',
                        style: const TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    muted('전체 ${m.n}건', size: 12),
                  ],
                ),
              ),
              MasterChart(points: curve),
            ],
          ),
        ),
        MasterPanel(
          title: '월별 손익',
          caption: '월별 수익과 손실을 비교하세요',
          action: muted('KRW', size: 10),
          child: MasterChart(points: groupedPoints(7), bars: true, height: 336),
        ),
      ),
      MasterPanel(
        title: '최근 거래',
        caption: '거래를 클릭하면 해당 매매일지가 열립니다.',
        action: TextButton(
          onPressed: () => widget.onSection(3),
          child: const Text('전체 보기 ›'),
        ),
        child: table(m.ordered.reversed.take(5).toList(), compact: true),
      ),
      cardGrid([
        MasterCard(
          label: '평균 수익률',
          value: '+${m.averageWin.toStringAsFixed(2)}%',
          color: masterMint,
        ),
        MasterCard(
          label: '평균 손실률',
          value: '−${m.averageLoss.toStringAsFixed(2)}%',
          color: masterRed,
        ),
        MasterCard(
          label: '평균 수익금',
          value: masterWon(m.wins.isEmpty ? 0 : m.grossProfit / m.wins.length),
        ),
        MasterCard(
          label: '평균 손실금',
          value: masterWon(
            m.losses.isEmpty ? 0 : m.grossLoss / m.losses.length,
          ),
        ),
      ]),
    ],
  );
  Widget periods(int length) {
    final groups = <String, List<Trade>>{};
    for (final t in m.ordered) {
      groups.putIfAbsent(t.exit.substring(0, length), () => []).add(t);
    }
    final names = groups.keys.toList()..sort((a, b) => b.compareTo(a));
    return Column(
      children: [
        MasterPanel(
          title: length == 7 ? '월별 손익 흐름' : '연도별 손익 흐름',
          child: MasterChart(points: groupedPoints(length), bars: true),
        ),
        MasterPanel(
          title: '기간별 상세 성적표',
          child: horizontalTable(
            ['기간', '총 손익', '거래수', '승률', '손익비', 'PF', '기대수익률', '매수총액'],
            [
              for (final name in [...names, '전체 합계 / 지표'])
                ...() {
                  final x = MasterMetrics(groups[name] ?? widget.trades);
                  return [
                    [
                      name,
                      masterWon(x.net),
                      '${x.n}건',
                      '${x.winRate.toStringAsFixed(1)}%',
                      ratio(x.rewardRisk),
                      ratio(x.profitFactor),
                      masterPct(x.expectancy),
                      masterWon(x.trades.fold<double>(0, (a, t) => a + t.buy)),
                    ],
                  ];
                }(),
            ],
            footer: '요약 지표는 전체 거래를 합쳐 계산합니다. 기간별 평균과 전체 거래의 지표는 계산 기준이 다릅니다.',
          ),
        ),
      ],
    );
  }

  Widget distribution({bool compact = false}) {
    const bounds = [
      -double.infinity,
      -10.0,
      -5.0,
      0.0,
      5.0,
      10.0,
      20.0,
      double.infinity,
    ];
    const labels = [
      '−10% 미만',
      '−10 ~ −5%',
      '−5 ~ 0%',
      '0 ~ +5%',
      '+5 ~ +10%',
      '+10 ~ +20%',
      '+20% 이상',
    ];
    final bins = List.generate(
      7,
      (i) => MasterMetrics(
        widget.trades.where((t) => t.roi >= bounds[i] && t.roi < bounds[i + 1]),
      ),
    );
    final variance = widget.trades.fold<double>(
      0,
      (a, t) => a + math.pow(t.roi - m.expectancy, 2),
    );
    final sd = m.n > 1 ? math.sqrt(variance / (m.n - 1)) : 0;
    final skew = m.n >= 3 && sd > 0
        ? m.n /
              ((m.n - 1) * (m.n - 2)) *
              widget.trades.fold<double>(
                0,
                (a, t) => a + math.pow((t.roi - m.expectancy) / sd, 3),
              )
        : null;
    return MasterPanel(
      title: '수익률 구간별 성과',
      caption: '구간은 하한 포함, 상한 미포함입니다.',
      child: Column(
        children: [
          if (!compact)
            MasterChart(
              points: List.generate(
                7,
                (i) => ChartPoint(labels[i], bins[i].n.toDouble()),
              ),
              bars: true,
              count: true,
            ),
          if (!compact)
            Padding(
              padding: const EdgeInsets.all(18),
              child: muted('수익률 왜도 (Skewness): ${ratio(skew)}'),
            ),
          horizontalTable(
            ['수익률 구간', '거래수', '총 손익', '평균 수익률'],
            [
              for (int i = 0; i < 7; i++)
                [
                  labels[i],
                  '${bins[i].n}건',
                  masterWon(bins[i].net),
                  bins[i].n == 0 ? '—' : masterPct(bins[i].expectancy),
                ],
            ],
          ),
        ],
      ),
    );
  }

  Widget victor() => Column(
    children: [
      cardGrid([
        MasterCard(
          label: '수익률 손익비',
          value: '${ratio(m.rewardRisk)} : 1',
          caption: '평균 수익률 ÷ 평균 손실률',
        ),
        MasterCard(label: '거래당 기대수익률', value: masterPct(m.expectancy)),
        const MasterCard(
          label: '비교 기준',
          value: '3.0 : 1',
          caption: 'Victor Sperandeo 기준',
        ),
      ]),
      MasterPanel(
        title: '거래별 수익률',
        caption:
            '평균 손실률의 3배: +${(m.averageLoss > 0 ? m.averageLoss * 3 : 10).toStringAsFixed(2)}%',
        child: MasterChart(
          points: m.ordered
              .map((t) => ChartPoint('${t.ticker} · ${t.exit}', t.roi))
              .toList(),
          scatter: true,
          percent: true,
          height: 380,
          reference: m.averageLoss > 0 ? m.averageLoss * 3 : 10,
        ),
      ),
    ],
  );
  Widget rView() => MasterPanel(
    title: '최초 위험 기준 R 분석',
    child: Padding(
      padding: const EdgeInsets.all(22),
      child: muted('기준 정보 부족 · 최초 매수가, 손절가, 수량이 있는 포지션 사이클만 R을 계산합니다.'),
    ),
  );

  @override
  Widget build(BuildContext context) => switch (widget.section) {
    0 => overview(),
    1 => periods(7),
    2 => periods(4),
    3 => MasterPanel(
      title: '청산 완료 거래',
      caption: '보유 거래는 위에서 관리하고, 청산 거래를 클릭해 복기하세요. 종목·계좌·태그·메모로 검색할 수 있습니다.',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: TextFormField(
              initialValue: widget.query,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search, size: 17),
                hintText: '종목·계좌·메모 검색',
              ),
              onChanged: widget.onSearch,
            ),
          ),
          table(
            m.ordered.reversed
                .where(
                  (t) =>
                      '${t.ticker} ${t.extra['account_name'] ?? ''} ${t.memo} ${(t.extra['tags'] as List? ?? []).join(' ')}'
                          .toLowerCase()
                          .contains(widget.query.toLowerCase()),
                )
                .toList(),
          ),
          for (final t in m.ordered.reversed.take(5))
            ExpansionTile(
              title: Text(
                '${t.ticker} · ${t.exit} 복기 메모',
                style: const TextStyle(fontSize: 13),
              ),
              children: [
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: muted(t.memo.isEmpty ? '메모 없음' : t.memo),
                ),
                TextButton(
                  onPressed: () => widget.onJournal(t),
                  child: const Text('매매일지 열기'),
                ),
              ],
            ),
        ],
      ),
    ),
    4 => victor(),
    5 => rView(),
    6 => distribution(),
    _ => const SizedBox.shrink(),
  };
}

Widget horizontalTable(
  List<String> headings,
  List<List<String>> rows, {
  String? footer,
}) => Column(
  crossAxisAlignment: CrossAxisAlignment.stretch,
  children: [
    SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        columnSpacing: 24,
        horizontalMargin: 20,
        headingTextStyle: const TextStyle(
          color: masterMuted,
          fontSize: 12,
          fontFamily: 'DMSans',
          fontFamilyFallback: ['NotoSansKR'],
        ),
        dataTextStyle: const TextStyle(
          fontSize: 13,
          color: Color(0xffc7d1df),
          fontFamily: 'DMSans',
          fontFamilyFallback: ['NotoSansKR'],
        ),
        columns: [for (final h in headings) DataColumn(label: Text(h))],
        rows: [
          for (final row in rows)
            DataRow(cells: [for (final v in row) DataCell(Text(v))]),
        ],
      ),
    ),
    if (footer != null)
      Padding(
        padding: const EdgeInsets.all(20),
        child: muted(footer, size: 12),
      ),
  ],
);

class ChartPoint {
  final String label;
  final double value;
  const ChartPoint(this.label, this.value);
}

class MasterChart extends StatefulWidget {
  final List<ChartPoint> points;
  final bool bars, scatter, percent, count;
  final double height;
  final double? reference;
  const MasterChart({
    super.key,
    required this.points,
    this.bars = false,
    this.scatter = false,
    this.percent = false,
    this.count = false,
    this.height = 280,
    this.reference,
  });
  @override
  State<MasterChart> createState() => _MasterChartState();
}

class _MasterChartState extends State<MasterChart> {
  int? selected;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, c) {
      void point(double x) {
        if (widget.points.isEmpty) return;
        setState(
          () => selected =
              ((x - 62) / (c.maxWidth - 84) * (widget.points.length - 1))
                  .round()
                  .clamp(0, widget.points.length - 1),
        );
      }

      return Padding(
        padding: const EdgeInsets.only(left: 6, right: 12, bottom: 10),
        child: Column(
          children: [
            MouseRegion(
              onHover: (e) => point(e.localPosition.dx),
              onExit: (_) => setState(() => selected = null),
              child: GestureDetector(
                onTapDown: (e) => point(e.localPosition.dx),
                child: SizedBox(
                  height: widget.height,
                  width: double.infinity,
                  child: CustomPaint(
                    painter: MasterChartPainter(
                      points: widget.points,
                      bars: widget.bars,
                      scatter: widget.scatter,
                      percent: widget.percent,
                      count: widget.count,
                      reference: widget.reference,
                      selected: selected,
                    ),
                  ),
                ),
              ),
            ),
            SizedBox(
              height: 26,
              child: selected != null && selected! < widget.points.length
                  ? Text(
                      '${widget.points[selected!].label}: ${widget.percent
                          ? masterPct(widget.points[selected!].value)
                          : widget.count
                          ? widget.points[selected!].value.round().toString()
                          : widget.reference != null
                          ? ratio(widget.points[selected!].value)
                          : masterWon(widget.points[selected!].value)}',
                      style: const TextStyle(fontSize: 12, color: masterMint),
                    )
                  : const SizedBox(),
            ),
          ],
        ),
      );
    },
  );
}

class MasterChartPainter extends CustomPainter {
  final List<ChartPoint> points;
  final bool bars, scatter, percent, count;
  final double? reference;
  final int? selected;
  MasterChartPainter({
    required this.points,
    required this.bars,
    required this.scatter,
    required this.percent,
    required this.count,
    this.reference,
    this.selected,
  });
  void text(
    Canvas canvas,
    String s,
    Offset p, {
    TextAlign align = TextAlign.left,
  }) {
    final t = TextPainter(
      text: TextSpan(
        text: s,
        style: const TextStyle(
          fontSize: 10,
          color: masterMuted,
          fontFamily: 'DMSans',
          fontFamilyFallback: ['NotoSansKR'],
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: align,
      maxLines: 1,
    )..layout(maxWidth: 120);
    t.paint(canvas, p);
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;
    const left = 56.0, top = 16.0;
    final width = math.max(1.0, size.width - left - 12),
        height = size.height - 52;
    double low = math.min(0, points.map((p) => p.value).reduce(math.min)),
        high = math.max(0, points.map((p) => p.value).reduce(math.max));
    if (reference != null) high = math.max(high, reference!);
    if (high == low) {
      high = low + 1;
    }
    final pad = (high - low) * .12;
    high += pad;
    if (low < 0) low -= pad;
    double y(double value) => top + (high - value) / (high - low) * height;
    double x(int i) =>
        left +
        (bars
                ? (i + .5) / points.length
                : (points.length == 1 ? 0.5 : i / (points.length - 1))) *
            width;
    final grid = Paint()
      ..color = masterBorder
      ..strokeWidth = .6;
    for (int i = 0; i < 5; i++) {
      final yy = top + i / 4 * height;
      for (double xx = left; xx < left + width; xx += 8) {
        canvas.drawLine(
          Offset(xx, yy),
          Offset(math.min(xx + 3, left + width), yy),
          grid,
        );
      }
      final v = high - i / 4 * (high - low);
      text(
        canvas,
        percent
            ? '${v.toStringAsFixed(0)}%'
            : count
            ? v.toStringAsFixed(0)
            : v.abs() >= 10000
            ? '${(v / 10000).toStringAsFixed(0)}만'
            : v.toStringAsFixed(1),
        Offset(2, yy - 5),
      );
    }
    canvas.drawLine(
      Offset(left, y(0)),
      Offset(left + width, y(0)),
      Paint()
        ..color = const Color(0xff445066)
        ..strokeWidth = .7,
    );
    if (reference != null) {
      final yy = y(reference!);
      for (double xx = left; xx < left + width; xx += 10) {
        canvas.drawLine(
          Offset(xx, yy),
          Offset(math.min(xx + 5, left + width), yy),
          Paint()..color = const Color(0xffd7c58d),
        );
      }
    }
    if (bars) {
      final w = math.min(36.0, width / points.length * .65);
      for (int i = 0; i < points.length; i++) {
        final rect = Rect.fromLTRB(
          x(i) - w / 2,
          math.min(y(0), y(points[i].value)),
          x(i) + w / 2,
          math.max(y(0), y(points[i].value)),
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(rect, const Radius.circular(3)),
          Paint()..color = masterSign(points[i].value),
        );
      }
    } else if (scatter) {
      for (int i = 0; i < points.length; i++) {
        canvas.drawCircle(
          Offset(x(i), y(points[i].value)),
          4,
          Paint()
            ..color = points[i].value >= (reference ?? double.infinity)
                ? masterMint
                : points[i].value > 0
                ? const Color(0xffd7c58d)
                : masterRed,
        );
      }
    } else {
      final path = Path();
      for (int i = 0; i < points.length; i++) {
        if (i == 0) {
          path.moveTo(x(i), y(points[i].value));
        } else {
          path.lineTo(x(i), y(points[i].value));
        }
      }
      final fill = Path.from(path)
        ..lineTo(x(points.length - 1), top + height)
        ..lineTo(x(0), top + height)
        ..close();
      canvas.drawPath(
        fill,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              masterMint.withValues(alpha: .22),
              masterMint.withValues(alpha: 0),
            ],
          ).createShader(Rect.fromLTWH(left, top, width, height)),
      );
      canvas.drawPath(
        path,
        Paint()
          ..color = masterMint
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5,
      );
    }
    final ticks = bars && points.length <= 7
        ? List.generate(points.length, (i) => i)
        : <int>{0, (points.length / 2).floor(), points.length - 1}.toList();
    for (final i in ticks) {
      final label = points[i].label.length > 13
          ? points[i].label.substring(points[i].label.length - 10)
          : points[i].label;
      text(
        canvas,
        label,
        Offset((x(i) - 24).clamp(left, left + width - 55), top + height + 13),
      );
    }
    if (selected != null && selected! < points.length) {
      canvas.drawLine(
        Offset(x(selected!), top),
        Offset(x(selected!), top + height),
        Paint()..color = masterMuted.withValues(alpha: .4),
      );
      canvas.drawCircle(
        Offset(x(selected!), y(points[selected!].value)),
        4,
        Paint()..color = masterMint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant MasterChartPainter old) => true;
}
