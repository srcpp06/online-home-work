// Same shape as the combined file the image builder generates (SPEC §3.3).
import 'package:test/test.dart';

import 'public/01_cart_test.dart' as f0;
import 'hidden/02_discount_test.dart' as f1;

void main() {
  group('public/01_cart_test.dart', f0.main);
  group('hidden/02_discount_test.dart', f1.main);
}
