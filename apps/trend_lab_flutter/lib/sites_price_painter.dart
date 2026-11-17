part of 'sites_review.dart';

/// Uses the reference Site's 960 x 430 chart geometry, including volume.
class SitesPricePainter extends CustomPainter {
  final Map<String, dynamic> report;
  final int window;
  final Set<int> averages;
  final int? hovered;
  SitesPricePainter(
    this.report, {
    required this.window,
    required this.averages,
    this.hovered,
  });
  @override
  void paint(Canvas canvas, Size size) {
    final all = report['bars'] as List,
        e = report['entryIndex'] as int,
        z = report['exitIndex'] as int;
    final start = math.max(0, e - window),
        end = math.min(all.length - 1, z + window),
        bars = all.sublist(start, end + 1);
    final keys = [for (final n in averages) 'ma$n', 'close'];
    final values = <double>[
      for (final b in bars)
        for (final k in keys)
          if (b[k] != null) (b[k] as num).toDouble(),
    ];
    if (values.isEmpty) {
      return;
    }
    final rawMin = values.reduce(math.min), rawMax = values.reduce(math.max);
    final padding = rawMax == rawMin
        ? math.max(rawMax.abs() * .05, 1.0)
        : (rawMax - rawMin) * .12;
    final min = rawMin - padding, max = rawMax + padding;
    const left = 15.0,
        right = 884.0,
        top = 36.0,
        plot = 248.0,
        volumeTop = 314.0,
        volumeHeight = 48.0;
    double x(int i) => left + i / math.max(1, bars.length - 1) * (right - left);
    double y(num v) => top + (max - v) / (max - min) * plot;
    canvas.save();
    canvas.scale(size.width / 960, size.height / 430);
    void text(
      String s,
      double xx,
      double yy, {
      Color color = siteMuted,
      double font = 13,
      int align = 0,
    }) {
      final p = TextPainter(
        text: TextSpan(
          text: s,
          style: TextStyle(color: color, fontSize: font),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      p.paint(
        canvas,
        Offset(
          xx -
              (align == 1
                  ? p.width / 2
                  : align == 2
                  ? p.width
                  : 0),
          yy,
        ),
      );
    }

    void dash(
      Offset a,
      Offset b,
      Color color, {
      double on = 4,
      double off = 5,
    }) {
      final delta = b - a, distance = delta.distance;
      if (distance == 0) {
        return;
      }
      final direction = delta / distance;
      for (double d = 0; d < distance; d += on + off) {
        canvas.drawLine(
          a + direction * d,
          a + direction * math.min(d + on, distance),
          Paint()..color = color,
        );
      }
    }

    for (int i = 0; i <= 4; i++) {
      final p = min + (max - min) * i / 4, yy = y(p);
      dash(Offset(left, yy), Offset(right, yy), const Color(0xff28384b), on: 3);
      text(money(p).replaceAll('원', ''), right + 12, yy - 7);
    }
    canvas.drawRect(
      Rect.fromLTWH(
        x(e - start),
        top,
        math.max(x(z - start) - x(e - start), 2),
        plot,
      ),
      Paint()..color = siteMint.withValues(alpha: .07),
    );
    for (final key in keys) {
      final path = Path();
      bool started = false;
      for (int i = 0; i < bars.length; i++) {
        final value = bars[i][key] as num?;
        if (value == null) {
          started = false;
          continue;
        }
        if (!started) {
          path.moveTo(x(i), y(value));
          started = true;
        } else {
          path.lineTo(x(i), y(value));
        }
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = (key == 'close'
              ? siteMint
              : averagesColors[int.parse(key.substring(2))]!)
          ..style = PaintingStyle.stroke
          ..strokeWidth = (key == 'close' ? 2.3 : 1.5)
          ..strokeJoin = StrokeJoin.round,
      );
    }
    for (final index in [e, z]) {
      final xx = x(index - start),
          yy = y(all[index]['close'] as num),
          color = index == e ? siteMint : const Color(0xff70a9fa);
      dash(Offset(xx, top), Offset(xx, top + plot), color);
      canvas.drawCircle(Offset(xx, yy), 5, Paint()..color = color);
      canvas.drawCircle(
        Offset(xx, yy),
        5,
        Paint()
          ..color = sitePanel
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
      text(
        index == e ? '진입' : '청산',
        xx + (e == z ? (index == e ? -18 : 18) : 0),
        5,
        color: color,
        align: 1,
      );
    }
    final maxVolume = math.max(
      1.0,
      bars.map((b) => (b['volume'] as num).toDouble()).reduce(math.max),
    );
    final width = math.max(1.0, (right - left) / bars.length * .55);
    for (int i = 0; i < bars.length; i++) {
      final height = (bars[i]['volume'] as num) / maxVolume * volumeHeight;
      canvas.drawRect(
        Rect.fromLTWH(
          x(i) - width / 2,
          volumeTop + volumeHeight - height,
          width,
          height,
        ),
        Paint()
          ..color =
              (i > 0 &&
                          (bars[i]['close'] as num) <
                              (bars[i - 1]['close'] as num)
                      ? const Color(0xffad5965)
                      : const Color(0xff3c7a68))
                  .withValues(alpha: .7),
      );
    }
    text('거래량', right + 12, volumeTop + 3, font: 12);
    final ticks = math.min(5, bars.length);
    for (int i = 0; i < ticks; i++) {
      final n = (i / math.max(1, ticks - 1) * (bars.length - 1)).round();
      text(
        (bars[n]['date'] as String).substring(2),
        x(n),
        399,
        align: i == 0
            ? 0
            : i == ticks - 1
            ? 2
            : 1,
      );
    }
    if (hovered != null && hovered! >= start && hovered! <= end) {
      final b = all[hovered!],
          xx = x(hovered! - start),
          yy = y(b['close'] as num);
      dash(
        Offset(xx, top),
        Offset(xx, volumeTop + volumeHeight),
        siteMuted,
        on: 3,
        off: 4,
      );
      canvas.drawCircle(Offset(xx, yy), 4, Paint()..color = Colors.white);
      final tooltipLeft = (xx - 50).clamp(0.0, 699.0).toDouble();
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(tooltipLeft, 35, 185, 88),
        const Radius.circular(8),
      );
      canvas.drawRRect(rect, Paint()..color = const Color(0xff0b1728));
      canvas.drawRRect(
        rect,
        Paint()
          ..color = const Color(0xff465d7c)
          ..style = PaintingStyle.stroke,
      );
      text(b['date'] as String, tooltipLeft + 13, 45, color: Colors.white);
      text(
        money(b['close'] as num),
        tooltipLeft + 13,
        68,
        color: siteMint,
        font: 15,
      );
      text(
        '거래량 ${money(b['volume'] as num).replaceAll('원', '')}주',
        tooltipLeft + 13,
        94,
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(SitesPricePainter old) =>
      old.report != report ||
      old.window != window ||
      old.hovered != hovered ||
      old.averages.length != averages.length ||
      !old.averages.containsAll(averages);
}
