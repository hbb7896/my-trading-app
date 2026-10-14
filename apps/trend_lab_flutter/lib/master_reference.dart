import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'master_metrics.dart';
import 'trade.dart';
import 'trading_master.dart' show masterSections;
import 'master_target.dart';

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
    final count = c.maxWidth < 660 ? 2 : cards.length;
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
  final Widget? journal;
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
  });
  static const icons = [
    Icons.dashboard_outlined,
    Icons.calendar_month_outlined,
    Icons.date_range_outlined,
    Icons.assignment_outlined,
    Icons.psychology_outlined,
    Icons.balance_outlined,
    Icons.track_changes_outlined,
    Icons.bar_chart_outlined,
    Icons.menu_book_outlined,
    Icons.chat_bubble_outline,
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
              const MasterDiamond(size: 26),
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
          for (int i = 0; i < 10; i++) ...[
            if (i == 5)
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
                        if (i == 4) badge('DNA'),
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
                                            : section == 4
                                            ? 'UNDERSTAND YOUR EDGE'
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
                                            : section == 4
                                            ? '숫자에 담긴 나의 매매 성향과 변화의 흐름을 확인하세요.'
                                            : '매매 기록을 바탕으로 거래 성과를 살펴보세요.',
                                        size: mobile ? 12 : 14,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                FilledButton.icon(
                                  onPressed: onNew,
                                  icon: const Icon(Icons.add, size: 18),
                                  label: const Text('거래 등록'),
                                ),
                              ],
                            ),
                            const SizedBox(height: 27),
                            toolbar(mobile),
                            const SizedBox(height: 20),
                            if (demo)
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
                            if (trades.isEmpty &&
                                !loading &&
                                ![8, 9].contains(section))
                              MasterPanel(
                                title: '아직 거래 기록이 없습니다',
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
      pair(
        MasterPanel(
          title: '최근 거래',
          caption: '거래를 클릭하면 해당 매매일지가 열립니다.',
          action: TextButton(
            onPressed: () => widget.onSection(3),
            child: const Text('전체 보기 ›'),
          ),
          child: table(m.ordered.reversed.take(5).toList(), compact: true),
        ),
        MasterPanel(
          title: '나의 Trading DNA',
          action: const Icon(
            Icons.psychology_outlined,
            color: masterMint,
            size: 21,
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 0, 22, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                badge('MY TRADING TYPE', color: masterMint),
                const SizedBox(height: 20),
                Text(
                  m.dnaType,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 10),
                muted(
                  m.dnaType == 'Trend Follower'
                      ? '작은 손실을 관리하며 큰 수익을 따라가는 매매 구조입니다.'
                      : '승률과 손익비, 큰 승자의 기여도를 함께 관찰해보세요.',
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          muted('평균 손익비'),
                          const SizedBox(height: 12),
                          Text(
                            '${ratio(m.rewardRisk)} : 1',
                            style: const TextStyle(fontSize: 23),
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          muted('Big Winner 기여도'),
                          const SizedBox(height: 12),
                          Text(
                            '${m.contribution.toStringAsFixed(1)}%',
                            style: const TextStyle(fontSize: 23),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const Divider(height: 38),
                Row(
                  children: [
                    Expanded(child: muted('최근 Edge 상태')),
                    badge(m.edgeStatus, color: masterMint),
                  ],
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => widget.onSection(4),
                    child: const Text('내 Trading DNA 살펴보기 ›'),
                  ),
                ),
              ],
            ),
          ),
        ),
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

  Widget holdingDna() {
    final valid = widget.trades.where((t) => (holding(t) ?? -1) >= 0).toList();
    const ranges = [
      (0, 0, '당일'),
      (1, 3, '1~3일'),
      (4, 10, '4~10일'),
      (11, 30, '11~30일'),
      (31, 90, '31~90일'),
      (91, 100000, '91일+'),
    ];
    return MasterPanel(
      title: 'Holding Period DNA',
      caption: '진입일과 청산일이 모두 있는 거래를 분석합니다.',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: cardGrid([
              MasterCard(label: '보유기간 데이터', value: '${valid.length}/${m.n}건'),
              MasterCard(
                label: '수익거래 평균 보유',
                value: '${m.averageDays(true)?.toStringAsFixed(1) ?? '—'}일',
              ),
              MasterCard(
                label: '손실거래 평균 보유',
                value: '${m.averageDays(false)?.toStringAsFixed(1) ?? '—'}일',
              ),
              MasterCard(
                label: 'Big Winner 평균 보유',
                value: m.big.where((t) => holding(t) != null).isEmpty
                    ? '—'
                    : '${mean(m.big.map(holding).whereType<int>()).toStringAsFixed(1)}일',
              ),
            ]),
          ),
          horizontalTable(
            ['보유구간', '거래수', '승률', 'PF', '기대수익률', '총 손익'],
            [
              for (final range in ranges)
                ...() {
                  final x = MasterMetrics(
                    valid.where(
                      (t) => holding(t)! >= range.$1 && holding(t)! <= range.$2,
                    ),
                  );
                  return x.n == 0
                      ? <List<String>>[]
                      : [
                          [
                            range.$3,
                            '${x.n}건',
                            '${x.winRate.toStringAsFixed(1)}%',
                            ratio(x.profitFactor),
                            masterPct(x.expectancy),
                            masterWon(x.net),
                          ],
                        ];
                }(),
            ],
          ),
        ],
      ),
    );
  }

  Widget dna() => Column(
    children: [
      MasterPanel(
        title: m.dnaType,
        caption: '${m.n}건의 기록을 바탕으로 한 매매 성향 · 최근 상태 ${m.edgeStatus}',
        child: const Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            'MY TRADING TYPE',
            style: TextStyle(color: masterMint, letterSpacing: 2),
          ),
        ),
      ),
      cardGrid([
        MasterCard(label: '승률', value: '${m.winRate.toStringAsFixed(1)}%'),
        MasterCard(label: '평균 손익비', value: ratio(m.rewardRisk)),
        MasterCard(label: 'Profit Factor', value: ratio(m.profitFactor)),
        MasterCard(label: '거래당 기대수익률', value: masterPct(m.expectancy)),
      ]),
      MasterPanel(
        title: 'Big Winner DNA',
        caption: 'Big Winner 기준: 수익률 +${m.bigThreshold.toStringAsFixed(2)}% 이상',
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: cardGrid([
                MasterCard(
                  label: '수익 기여도',
                  value: '${m.contribution.toStringAsFixed(1)}%',
                ),
                MasterCard(label: 'Big Winner 거래', value: '${m.big.length}건'),
                MasterCard(
                  label: '상위 10% 수익 기여',
                  value: '${topContribution().toStringAsFixed(1)}%',
                ),
              ]),
            ),
            table(m.big.reversed.toList(), compact: true),
          ],
        ),
      ),
      holdingDna(),
      MasterPanel(
        title: 'Risk DNA',
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: cardGrid([
            MasterCard(
              label: '평균 손실률',
              value: '−${m.averageLoss.toStringAsFixed(2)}%',
            ),
            MasterCard(
              label: '최대 손실률',
              value:
                  '−${widget.trades.fold<double>(0, (a, t) => math.max(a, -t.roi)).toStringAsFixed(2)}%',
            ),
            MasterCard(label: '최대 연속 손실', value: '${m.streak(false)}회'),
            MasterCard(label: '최대 연속 수익', value: '${m.streak(true)}회'),
          ]),
        ),
      ),
      MasterPanel(
        title: 'Edge Change Detection',
        caption: '최근 20거래와 직전 최대 20거래 비교',
        child: m.previous.n < 5
            ? Padding(
                padding: const EdgeInsets.all(22),
                child: muted('구간 비교에는 최소 25건의 거래가 필요합니다.'),
              )
            : horizontalTable(
                [
                  '지표',
                  '전체',
                  '직전 ${m.previous.n}거래',
                  '최근 ${m.recent.n}거래',
                  '변화',
                ],
                [
                  for (final key in [
                    '승률',
                    'Profit Factor',
                    '손익비',
                    '기대수익률',
                    '평균 수익률',
                    '평균 손실률',
                  ])
                    ...() {
                      double? read(MasterMetrics x) => switch (key) {
                        '승률' => x.winRate,
                        'Profit Factor' => x.profitFactor,
                        '손익비' => x.rewardRisk,
                        '기대수익률' => x.expectancy,
                        '평균 수익률' => x.averageWin,
                        _ => x.averageLoss,
                      };
                      final a = read(m.previous), b = read(m.recent);
                      return [
                        [
                          key,
                          ratio(read(m)),
                          ratio(a),
                          ratio(b),
                          a == null || b == null || !a.isFinite || !b.isFinite
                              ? '—'
                              : (b - a).toStringAsFixed(2),
                        ],
                      ];
                    }(),
                ],
              ),
      ),
      distribution(compact: true),
    ],
  );
  double topContribution() {
    final wins = m.wins..sort((a, b) => b.pnl.compareTo(a.pnl));
    return m.grossProfit == 0
        ? 0
        : wins
                  .take(math.max(1, (wins.length * .1).ceil()))
                  .fold<double>(0, (a, t) => a + t.pnl) /
              m.grossProfit *
              100;
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
  Widget rView() {
    final risk = m.losses.isEmpty ? 0 : m.grossLoss / m.losses.length;
    double total = 0;
    return risk == 0
        ? MasterPanel(
            title: 'R-배수 분석',
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: muted('평균 손실금으로 1R을 정의합니다. 손실 거래가 없어 R-배수를 계산할 수 없습니다.'),
            ),
          )
        : Column(
            children: [
              cardGrid([
                MasterCard(
                  label: '나의 1R',
                  value: masterWon(risk),
                  caption: '선택 기간의 평균 손실금',
                ),
                MasterCard(
                  label: '평균 R-배수',
                  value: '${(m.net / m.n / risk).toStringAsFixed(2)}R',
                ),
                MasterCard(
                  label: '최고 R-배수',
                  value:
                      '${(widget.trades.map((t) => t.pnl).reduce(math.max) / risk).toStringAsFixed(2)}R',
                ),
              ]),
              MasterPanel(
                title: '누적 R-배수',
                caption: '거래 순서에 따른 누적 성과',
                child: MasterChart(
                  points: List.generate(
                    m.n,
                    (i) => ChartPoint(
                      '${i + 1}번째',
                      total += m.ordered[i].pnl / risk,
                    ),
                  ),
                ),
              ),
            ],
          );
  }

  Widget minervini() {
    final years =
        widget.trades.map((t) => t.exit.substring(0, 4)).toSet().toList()
          ..sort((a, b) => b.compareTo(a));
    if (years.isEmpty) years.add(DateTime.now().year.toString());
    final selected = years.contains(year) ? year! : years.first;
    final x = MasterMetrics(
      widget.trades.where((t) => t.exit.startsWith(selected)),
    );
    String pct(MasterMetrics v, bool win) => (win ? v.wins : v.losses).isEmpty
        ? '—'
        : '${(win ? v.averageWin : v.averageLoss).toStringAsFixed(2)}%';
    return Column(
      children: [
        MasterPanel(
          title: '승률보다, 수익과 손실의 균형.',
          caption: '월별 수익·손실과 보유기간을 함께 비교하는 매매 점검표',
          action: DropdownButton<String>(
            value: selected,
            items: [
              for (final y in years)
                DropdownMenuItem(value: y, child: Text('$y년')),
            ],
            onChanged: (v) => setState(() => year = v),
          ),
          child: const Padding(
            padding: EdgeInsets.all(20),
            child: Text(
              'MINERVINI JOURNAL',
              style: TextStyle(color: masterMint, letterSpacing: 2),
            ),
          ),
        ),
        cardGrid([
          MasterCard(
            label: '성공률',
            value: x.n == 0 ? '—' : '${x.winRate.toStringAsFixed(2)}%',
            caption:
                '수익 ${x.wins.length} · 손실 ${x.losses.length} · 본전 ${x.n - x.wins.length - x.losses.length}건',
          ),
          MasterCard(
            label: '평균 수익 / 평균 손실',
            value: '${pct(x, true)} / ${pct(x, false)}',
            caption: '개별 거래 수익률의 산술평균',
          ),
          MasterCard(
            label: '성공 / 실패 비율',
            value: '${ratio(x.rewardRisk)} : 1',
            caption: '평균 수익률 ÷ 평균 손실률',
          ),
          MasterCard(
            label: '조정 후 성공 / 실패 비율',
            value: '${ratio(x.adjustedRewardRisk)} : 1',
            caption: '승률과 손실 거래 비중을 반영',
          ),
        ]),
        MasterPanel(
          title: '월별 확인표',
          caption: '$selected년 · 상단의 분석 기간 필터 적용 · 청산일 기준',
          child: horizontalTable(
            [
              '월',
              '평균 수익',
              '평균 손실',
              '승률',
              '총 거래수',
              '장기 수익',
              '장기 손실',
              '수익 일수 평균',
              '손실 일수 평균',
            ],
            [
              for (int i = 1; i <= 12; i++)
                ...() {
                  final month = '$selected-${i.toString().padLeft(2, '0')}';
                  final c = MasterMetrics(
                        widget.trades.where((t) => t.exit.startsWith(month)),
                      ),
                      l = MasterMetrics(
                        widget.trades.where(
                          (t) => t.exit.substring(0, 7).compareTo(month) <= 0,
                        ),
                      );
                  return [
                    [
                      '$i월',
                      pct(c, true),
                      pct(c, false),
                      c.n == 0 ? '—' : '${c.winRate.toStringAsFixed(2)}%',
                      '${c.n}건',
                      pct(l, true),
                      pct(l, false),
                      '${c.averageDays(true)?.toStringAsFixed(1) ?? '—'}일',
                      '${c.averageDays(false)?.toStringAsFixed(1) ?? '—'}일',
                    ],
                  ];
                }(),
              [
                '전체 / 평균',
                pct(x, true),
                pct(x, false),
                x.n == 0 ? '—' : '${x.winRate.toStringAsFixed(2)}%',
                '${x.n}건',
                pct(
                  MasterMetrics(
                    widget.trades.where(
                      (t) => t.exit.substring(0, 4).compareTo(selected) <= 0,
                    ),
                  ),
                  true,
                ),
                pct(
                  MasterMetrics(
                    widget.trades.where(
                      (t) => t.exit.substring(0, 4).compareTo(selected) <= 0,
                    ),
                  ),
                  false,
                ),
                '${x.averageDays(true)?.toStringAsFixed(1) ?? '—'}일',
                '${x.averageDays(false)?.toStringAsFixed(1) ?? '—'}일',
              ],
            ],
            footer:
                '장기 수익·손실은 현재 기간 필터에 포함된 기록의 시작부터 각 월말까지 누적한 수익·손실 거래 평균입니다.',
          ),
        ),
        holdingDna(),
        TargetCalculator(stats: x),
        const SizedBox(height: 22),
        MasterPanel(
          title: '계산 기준 확인',
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: muted(
              '성공률 = 수익 거래수 ÷ 전체 거래수 × 100. 본전 거래도 전체 거래수에 포함합니다.\n조정 비율 = (평균 수익률 × 수익 거래수) ÷ (평균 손실률 × 손실 거래수).\n해당 거래가 없어 평균을 구할 수 없으면 —, 수익은 있고 손실이 없으면 비율을 ∞로 표시합니다.',
            ),
          ),
        ),
      ],
    );
  }

  Widget mentor() {
    final large = m.losses.isEmpty
        ? null
        : m.losses.map((t) => -t.roi).reduce(math.max);
    final avgBuy = mean(widget.trades.map((t) => t.buy)),
        size = avgBuy > 0
            ? widget.trades.map((t) => t.buy).reduce(math.max) / avgBuy
            : null;
    final risk =
        large != null && m.losses.length >= 3 && large >= m.averageLoss * 2;
    final edge = m.n >= 5 && (m.adjustedRewardRisk ?? 0) < 1;
    final sizeAttention = m.n >= 5 && (size ?? 0) >= 2;
    final holdAttention =
        m.wins.where((t) => holding(t) != null).length >= 3 &&
        m.losses.where((t) => holding(t) != null).length >= 3 &&
        (m.averageDays(false) ?? 0) > (m.averageDays(true) ?? 0);
    final pillars = [
      (
        '수익과 손실의 균형',
        '승률보다 수익·손실의 균형을 먼저 확인한다.',
        '승률 ${m.winRate.toStringAsFixed(2)}% · 평균 수익 ${masterPct(m.averageWin)} · 평균 손실 ${m.averageLoss.toStringAsFixed(2)}% · 조정 손익비 ${ratio(m.adjustedRewardRisk)}',
        m.n < 5
            ? '진입과 청산의 기준을 일관되게 기록하세요.'
            : edge
            ? '목표 수익부터 높이기보다 큰 손실의 청산 과정과 작게 끝난 수익 거래를 각각 복기하세요.'
            : '성과를 만든 진입·청산 기준을 유지하고, 이 결과만으로 매수 규모를 확대하지 마세요.',
        edge,
      ),
      (
        '손실을 작게 관리하기',
        '손실을 인정할 기준을 진입 전에 정한다.',
        large == null
            ? '선택 기간에 손실 거래가 없습니다.'
            : '최대 손실 ${large.toStringAsFixed(2)}% · 평균 손실 ${m.averageLoss.toStringAsFixed(2)}% · 손실 ${m.losses.length}건',
        risk
            ? '최대 손실이 평균의 2배 이상입니다. 사전에 정한 청산 기준과 실행을 늦춘 이유를 확인하세요.'
            : '최초 계획과 실제 청산 사유를 비교하고 감당할 원화 손실 한도를 적어두세요.',
        risk,
      ),
      (
        '매수 규모와 위험의 일관성',
        '확신과 실제로 감당할 위험금액을 구분한다.',
        size == null
            ? '매수 규모를 비교할 기록이 없습니다.'
            : '최대 매수총액 / 평균 매수총액 ${size.toStringAsFixed(2)}배',
        '총 매수금액은 분할 매수나 재매수도 포함할 수 있습니다. 실제 보유금액, 청산 기준과 예상 원화 손실을 함께 계산하세요.',
        sizeAttention,
      ),
      (
        '승자와 패자의 보유 습관',
        '수익과 손실 거래의 청산 이유를 비교한다.',
        '수익 평균 ${m.averageDays(true)?.toStringAsFixed(1) ?? '—'}일 · 손실 평균 ${m.averageDays(false)?.toStringAsFixed(1) ?? '—'}일',
        holdAttention
            ? '손실 거래를 수익 거래보다 오래 보유했습니다. 회복을 기대하며 기준을 바꾼 거래와 수익을 일찍 청산한 거래가 있었는지 확인하세요.'
            : '보유일수보다 계획한 청산 조건을 실행했는지 살펴보세요. 승자와 패자의 청산 근거를 나란히 비교하세요.',
        holdAttention,
      ),
    ];
    final attention = pillars.where((p) => p.$5).toList();
    final verdict = m.n == 0
        ? '첫 기록을 기다리는 중'
        : m.n < 20
        ? '작은 표본, 일관된 기록부터'
        : attention.isEmpty
        ? '기준을 유지하며 검증하기'
        : '${attention.first.$1}부터 점검';
    return Column(
      children: [
        MasterPanel(
          title: '미너비니라면, 무엇을 먼저 점검했을까?',
          caption: '손실 통제와 규율의 관점으로 나의 매매 기록을 돌아봅니다.',
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: muted(
              '미너비니의 원칙을 참고해 구성한 저널 분석입니다. 실제 미너비니의 발언이나 공식 평가가 아닙니다.${widget.demo ? ' 현재 평가는 샘플 기록을 사용합니다.' : ''}',
            ),
          ),
        ),
        MasterPanel(
          title: verdict,
          caption: 'FIRST THING TO REVIEW · ${m.n}건의 거래',
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: muted(
              m.n < 20
                  ? '같은 기준으로 거래를 기록하고, 진입과 청산 근거를 남기세요.'
                  : attention.isEmpty
                  ? '계획을 지킨 거래와 그렇지 않은 거래를 구분해 다음 거래의 준비에 활용하세요.'
                  : attention.first.$4,
            ),
          ),
        ),
        for (final p in pillars)
          MasterPanel(
            title: p.$1,
            action: badge(
              p.$5 ? '우선 점검' : '기준 확인',
              color: p.$5 ? const Color(0xffd7c58d) : masterMint,
            ),
            caption: p.$2,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(22, 0, 22, 22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  muted('기록에서 확인한 점', size: 11),
                  const SizedBox(height: 8),
                  Text(p.$3, style: const TextStyle(height: 1.7)),
                  const Divider(height: 28),
                  muted('복기할 행동', size: 11),
                  const SizedBox(height: 8),
                  Text(p.$4, style: const TextStyle(height: 1.7)),
                ],
              ),
            ),
          ),
        MasterPanel(
          title: '최근 매매에서 달라진 점',
          caption: '선택 기간 내 최근 20거래와 직전 최대 20거래 비교',
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: muted(
              m.previous.n < 5
                  ? '선택 기간에 25건 이상 쌓이면 최근 흐름을 비교합니다.'
                  : '거래당 평균 수익률 ${masterPct(m.previous.expectancy)} → ${masterPct(m.recent.expectancy)}\n평균 손실률 ${m.previous.averageLoss.toStringAsFixed(2)}% → ${m.recent.averageLoss.toStringAsFixed(2)}%',
            ),
          ),
        ),
        MasterPanel(
          title: '다음 10거래에서 실천할 세 가지',
          caption: '체크한 항목은 이 탭을 열어둔 동안만 표시합니다.',
          child: Column(
            children: [
              for (int i = 0; i < 3; i++)
                CheckboxListTile(
                  value: checked.contains(i),
                  onChanged: (v) => setState(() {
                    if (v == true) {
                      checked.add(i);
                    } else {
                      checked.remove(i);
                    }
                  }),
                  title: Text(['진입 전', '거래 중', '청산 후'][i]),
                  subtitle: Text(
                    [
                      '진입 이유, 청산 조건, 감당할 원화 손실 한도를 기록하세요.',
                      '가격이 불리하게 움직일 때 최초 청산 기준을 바꾸고 싶은 이유를 기록하세요.',
                      '예상한 청산 조건과 실제 청산 사유를 비교하세요.',
                    ][i],
                  ),
                  controlAffinity: ListTileControlAffinity.leading,
                ),
            ],
          ),
        ),
        MasterPanel(
          title: '기록만으로 판단할 수 없는 것',
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: muted(
              '현재 기록만으로 진입 시점의 추세·상대강도·거래량·VCP·SEPA 조건, 최초 손절선, 계좌 잔고와 동시 보유 금액을 알 수 없습니다. 따라서 진입의 질이나 실제 계좌 위험 비중은 평가하지 않습니다.',
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => switch (widget.section) {
    0 => overview(),
    1 => periods(7),
    2 => periods(4),
    3 => MasterPanel(
      title: '전체 거래 기록',
      caption: '거래를 클릭해 복기하세요. 종목, 실수 태그, 메모로 검색할 수 있습니다.',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: TextFormField(
              initialValue: widget.query,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search, size: 17),
                hintText: '종목 또는 메모 검색',
              ),
              onChanged: widget.onSearch,
            ),
          ),
          table(
            m.ordered.reversed
                .where(
                  (t) =>
                      '${t.ticker} ${t.memo} ${(t.extra['tags'] as List? ?? []).join(' ')}'
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
    4 => dna(),
    5 => victor(),
    6 => rView(),
    7 => distribution(),
    8 => minervini(),
    _ => mentor(),
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
