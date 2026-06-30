#!/usr/bin/env node
/* global __dirname */

const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const yamapRoot = path.join(projectRoot, "node_modules", "react-native-yamap");
const yamapPackageJsonPath = path.join(yamapRoot, "package.json");
const templateRoot = path.join(projectRoot, "scripts", "react-native-yamap-patches");

function readFile(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function writeFile(filePath, contents) {
  fs.writeFileSync(filePath, contents);
}

function copyPatchedFile(relativePath) {
  const sourcePath = path.join(templateRoot, relativePath);
  const targetPath = path.join(yamapRoot, relativePath);

  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Expected patch template not found: ${relativePath}`);
  }

  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.copyFileSync(sourcePath, targetPath);
  console.log(`copied react-native-yamap patch template for ${relativePath}`);
}

function replaceOnce(contents, from, to, label) {
  if (contents.includes(to)) {
    return contents;
  }

  const candidates = Array.isArray(from) ? from : [from];

  for (const candidate of candidates) {
    if (contents.includes(candidate)) {
      return contents.replace(candidate, to);
    }
  }

  throw new Error(`Expected snippet not found while patching ${label}`);
}

function applyReplacements(relativePath, replacements) {
  const filePath = path.join(yamapRoot, relativePath);
  let contents = readFile(filePath);

  for (const [from, to] of replacements) {
    contents = replaceOnce(contents, from, to, relativePath);
  }

  writeFile(filePath, contents);
  console.log(`patched react-native-yamap/${relativePath}`);
}

if (!fs.existsSync(yamapPackageJsonPath)) {
  console.log("react-native-yamap is not installed; skipping local patch");
  process.exit(0);
}

const yamapPackageJson = JSON.parse(readFile(yamapPackageJsonPath));
if (yamapPackageJson.version !== "4.8.3") {
  console.warn(
    `react-native-yamap version ${yamapPackageJson.version} is installed; the local RN 0.81 patch was written for 4.8.3`
  );
}

const managerPath = "android/src/main/java/ru/vvdev/yamap";

applyReplacements("android/build.gradle", [
  [
    `    implementation 'com.google.android.gms:play-services-location:+'\n`,
    `    implementation 'com.google.android.gms:play-services-location:21.0.1'\n`,
  ],
]);

applyReplacements(`${managerPath}/ClusteredYamapViewManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
  [
    `            "getScreenPoints" -> if (args != null) {\n                view.emitWorldToScreenPoints(args.getArray(0), args.getString(1))\n            }\n`,
    `            "getScreenPoints" -> if (args != null) {\n                args.getArray(0)?.let { view.emitWorldToScreenPoints(it, args.getString(1)) }\n            }\n`,
  ],
  [
    `            "getWorldPoints" -> if (args != null) {\n                view.emitScreenToWorldPoints(args.getArray(0), args.getString(1))\n            }\n`,
    `            "getWorldPoints" -> if (args != null) {\n                args.getArray(0)?.let { view.emitScreenToWorldPoints(it, args.getString(1)) }\n            }\n`,
  ],
  [
    `        castToYaMapView(view).setClusteredMarkers(points.toArrayList())\n`,
    `        castToYaMapView(view).setClusteredMarkers(ArrayList(points.toArrayList().filterNotNull()))\n`,
  ],
  [
    `        jsVehicles: ReadableArray?,\n        id: String\n`,
    `        jsVehicles: ReadableArray?,\n        id: String?\n`,
  ],
  [
    `                    vehicles.add(jsVehicles.getString(i))\n`,
    `                    jsVehicles.getString(i)?.let(vehicles::add)\n`,
  ],
  [
    `            .build()\n    }\n\n    override fun getCommandsMap(): Map<String, Int>? {\n`,
    `            .build() as MutableMap<String, Any>\n    }\n\n    override fun getCommandsMap(): Map<String, Int>? {\n`,
  ],
]);

applyReplacements(`${managerPath}/YamapViewManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
  [
    `            "getScreenPoints" -> if (args != null) {\n                view.emitWorldToScreenPoints(args.getArray(0), args.getString(1))\n            }\n`,
    `            "getScreenPoints" -> if (args != null) {\n                args.getArray(0)?.let { view.emitWorldToScreenPoints(it, args.getString(1)) }\n            }\n`,
  ],
  [
    `            "getWorldPoints" -> if (args != null) {\n                view.emitScreenToWorldPoints(args.getArray(0), args.getString(1))\n            }\n`,
    `            "getWorldPoints" -> if (args != null) {\n                args.getArray(0)?.let { view.emitScreenToWorldPoints(it, args.getString(1)) }\n            }\n`,
  ],
  [
    `        jsVehicles: ReadableArray?,\n        id: String\n`,
    `        jsVehicles: ReadableArray?,\n        id: String?\n`,
  ],
  [
    `                    vehicles.add(jsVehicles.getString(i))\n`,
    `                    jsVehicles.getString(i)?.let(vehicles::add)\n`,
  ],
  [
    `            .build()\n    }\n\n    override fun getCommandsMap(): Map<String, Int>? {\n`,
    `            .build() as MutableMap<String, Any>\n    }\n\n    override fun getCommandsMap(): Map<String, Int>? {\n`,
  ],
]);

applyReplacements(`${managerPath}/YamapMarkerManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .put("onPress", MapBuilder.of("registrationName", "onPress"))\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf("onPress" to MapBuilder.of("registrationName", "onPress"))\n    }\n`,
  ],
  [
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
  [
    `                val markerPoint = args!!.getMap(0)\n`,
    `                val markerPoint = args!!.getMap(0) ?: return\n`,
  ],
]);

applyReplacements(`${managerPath}/YamapCircleManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .put("onPress", MapBuilder.of("registrationName", "onPress"))\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf("onPress" to MapBuilder.of("registrationName", "onPress"))\n    }\n`,
  ],
  [
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
]);

applyReplacements(`${managerPath}/YamapPolygonManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .put("onPress", MapBuilder.of("registrationName", "onPress"))\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf("onPress" to MapBuilder.of("registrationName", "onPress"))\n    }\n`,
  ],
  [
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
]);

applyReplacements(`${managerPath}/YamapPolylineManager.kt`, [
  [
    `    override fun getExportedCustomDirectEventTypeConstants(): Map<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .put("onPress", MapBuilder.of("registrationName", "onPress"))\n            .build()\n    }\n`,
    `    override fun getExportedCustomDirectEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf("onPress" to MapBuilder.of("registrationName", "onPress"))\n    }\n`,
  ],
  [
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return MapBuilder.builder<String, Any>()\n            .build()\n    }\n`,
    `    override fun getExportedCustomBubblingEventTypeConstants(): MutableMap<String, Any>? {\n        return mutableMapOf()\n    }\n`,
  ],
]);

applyReplacements("android/src/main/java/ru/vvdev/yamap/view/YamapView.kt", [
  [
    `            val p = worldPoints.getMap(i)\n`,
    `            val p = worldPoints.getMap(i) ?: continue\n`,
  ],
  [
    `            val p = screenPoints.getMap(i)\n`,
    `            val p = screenPoints.getMap(i) ?: continue\n`,
  ],
  [
    `            wTransports.putArray(key, Arguments.fromList(value))\n`,
    `            val transportNames = value?.filterNotNull()?.map { it as Any } ?: emptyList()\n            wTransports.putArray(key, Arguments.fromList(transportNames))\n`,
  ],
]);

applyReplacements("ios/View/RNYMView.m", [
  [
    [
      `- (void)insertReactSubview:(UIView<RCTComponent> *)subview atIndex:(NSInteger)atIndex {\n    if ([subview isKindOfClass:[YamapPolygonView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolygonView *polygon = (YamapPolygonView *) subview;\n        YMKPolygonMapObject *obj = [objects addPolygonWithPolygon:[polygon getPolygon]];\n        [polygon setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapPolylineView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolylineView *polyline = (YamapPolylineView*) subview;\n        YMKPolylineMapObject *obj = [objects addPolylineWithPolyline:[polyline getPolyline]];\n        [polyline setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapMarkerView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapMarkerView *marker = (YamapMarkerView *) subview;\n        YMKPlacemarkMapObject *obj = [objects addPlacemarkWithPoint:[marker getPoint]];\n        [marker setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapCircleView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapCircleView *circle = (YamapCircleView*) subview;\n        YMKCircleMapObject *obj = [objects addCircleWithCircle:[circle getCircle]];\n        [circle setMapObject:obj];\n    } else {\n        NSArray<id<RCTComponent>> *childSubviews = [subview reactSubviews];\n        for (int i = 0; i < childSubviews.count; i++) {\n            [self insertReactSubview:(UIView *)childSubviews[i] atIndex:atIndex];\n        }\n    }\n\n    [_reactSubviews insertObject:subview atIndex:atIndex];\n    [super insertReactSubview:subview atIndex:atIndex];\n}\n`,
      `- (void)insertReactSubview:(UIView<RCTComponent> *)subview atIndex:(NSInteger)atIndex {\n    if ([subview isKindOfClass:[YamapPolygonView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolygonView *polygon = (YamapPolygonView *) subview;\n        YMKPolygonMapObject *obj = [objects addPolygonWithPolygon:[polygon getPolygon]];\n        [polygon setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapPolylineView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolylineView *polyline = (YamapPolylineView*) subview;\n        YMKPolylineMapObject *obj = [objects addPolylineWithPolyline:[polyline getPolyline]];\n        [polyline setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapMarkerView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapMarkerView *marker = (YamapMarkerView *) subview;\n        YMKPlacemarkMapObject *obj = [objects addPlacemarkWithPoint:[marker getPoint]];\n        [marker setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapCircleView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapCircleView *circle = (YamapCircleView*) subview;\n        YMKCircleMapObject *obj = [objects addCircleWithCircle:[circle getCircle]];\n        [circle setMapObject:obj];\n    } else {\n        NSArray<id<RCTComponent>> *childSubviews = [subview reactSubviews];\n        for (int i = 0; i < childSubviews.count; i++) {\n            [self insertReactSubview:(UIView *)childSubviews[i] atIndex:atIndex];\n        }\n    }\n\n    NSInteger safeIndex = MAX((NSInteger)0, MIN(atIndex, (NSInteger)_reactSubviews.count));\n    [_reactSubviews insertObject:subview atIndex:safeIndex];\n    [super insertReactSubview:subview atIndex:safeIndex];\n}\n`,
    ],
    `- (void)insertReactSubview:(UIView<RCTComponent> *)subview atIndex:(NSInteger)atIndex {\n    if (subview == nil) {\n        return;\n    }\n    if ([subview isKindOfClass:[YamapPolygonView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolygonView *polygon = (YamapPolygonView *) subview;\n        YMKPolygonMapObject *obj = [objects addPolygonWithPolygon:[polygon getPolygon]];\n        [polygon setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapPolylineView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapPolylineView *polyline = (YamapPolylineView*) subview;\n        YMKPolylineMapObject *obj = [objects addPolylineWithPolyline:[polyline getPolyline]];\n        [polyline setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapMarkerView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapMarkerView *marker = (YamapMarkerView *) subview;\n        YMKPlacemarkMapObject *obj = [objects addPlacemarkWithPoint:[marker getPoint]];\n        [marker setMapObject:obj];\n    } else if ([subview isKindOfClass:[YamapCircleView class]]) {\n        YMKMapObjectCollection *objects = self.mapWindow.map.mapObjects;\n        YamapCircleView *circle = (YamapCircleView*) subview;\n        YMKCircleMapObject *obj = [objects addCircleWithCircle:[circle getCircle]];\n        [circle setMapObject:obj];\n    } else {\n        NSArray<id<RCTComponent>> *childSubviews = [subview reactSubviews];\n        for (int i = 0; i < childSubviews.count; i++) {\n            [self insertReactSubview:(UIView *)childSubviews[i] atIndex:atIndex];\n        }\n    }\n\n    NSInteger safeIndex = MAX((NSInteger)0, MIN(atIndex, (NSInteger)_reactSubviews.count));\n    [_reactSubviews insertObject:subview atIndex:safeIndex];\n    [super insertReactSubview:subview atIndex:safeIndex];\n}\n`,
  ],
  [
    [
      `- (void)insertMarkerReactSubview:(UIView<RCTComponent> *) subview atIndex:(NSInteger) atIndex {\n    [_reactSubviews insertObject:subview atIndex:atIndex];\n    [super insertReactSubview:subview atIndex:atIndex];\n}\n`,
      `- (void)insertMarkerReactSubview:(UIView<RCTComponent> *) subview atIndex:(NSInteger) atIndex {\n    NSInteger safeIndex = MAX((NSInteger)0, MIN(atIndex, (NSInteger)_reactSubviews.count));\n    [_reactSubviews insertObject:subview atIndex:safeIndex];\n    [super insertReactSubview:subview atIndex:safeIndex];\n}\n`,
    ],
    `- (void)insertMarkerReactSubview:(UIView<RCTComponent> *) subview atIndex:(NSInteger) atIndex {\n    if (subview == nil) {\n        return;\n    }\n    NSInteger safeIndex = MAX((NSInteger)0, MIN(atIndex, (NSInteger)_reactSubviews.count));\n    [_reactSubviews insertObject:subview atIndex:safeIndex];\n    [super insertReactSubview:subview atIndex:safeIndex];\n}\n`,
  ],
]);

[
  "src/components/ClusteredYamap.tsx",
  "build/components/ClusteredYamap.js",
  "build/components/ClusteredYamap.d.ts",
  "ios/View/RNCYMView.h",
  "ios/View/RNCYMView.m",
  "ios/ClusteredYamapView.m",
  "android/src/main/java/ru/vvdev/yamap/RNYamapModule.kt",
  "android/src/main/java/ru/vvdev/yamap/view/ClusteredYamapView.kt",
  "android/src/main/java/ru/vvdev/yamap/ClusteredYamapViewManager.kt",
].forEach(copyPatchedFile);
