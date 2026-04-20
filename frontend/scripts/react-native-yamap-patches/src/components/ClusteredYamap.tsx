import React from 'react';
import {
  Platform,
  requireNativeComponent,
  NativeModules,
  UIManager,
  findNodeHandle,
  ViewProps,
  ImageSourcePropType,
  NativeSyntheticEvent,
} from 'react-native';
// @ts-ignore
import resolveAssetSource from 'react-native/Libraries/Image/resolveAssetSource';
import CallbacksManager from '../utils/CallbacksManager';
import {
  Animation,
  Point,
  DrivingInfo,
  MasstransitInfo,
  RoutesFoundEvent,
  Vehicles,
  CameraPosition,
  VisibleRegion,
  ScreenPoint,
  MapLoaded,
  InitialRegion,
  YandexLogoPosition,
  YandexLogoPadding
} from '../interfaces';
import { processColorProps } from '../utils';
import { YaMap } from './Yamap';

const { yamap: NativeYamapModule } = NativeModules;

export type ClusteredMarkerData = Record<string, unknown>;

export type ClusteredMarker<T extends ClusteredMarkerData = ClusteredMarkerData> = {
  point: Point;
  data?: T;
  iconKey?: string;
};

export type ClusteredMarkerPressEvent<T extends ClusteredMarkerData = ClusteredMarkerData> =
  NativeSyntheticEvent<{
    point: Point;
    data?: T;
    iconKey?: string;
  }>;

export interface ClusteredYaMapProps<T extends ClusteredMarkerData = ClusteredMarkerData> extends ViewProps {
  userLocationIcon?: ImageSourcePropType;
  userLocationIconScale?: number;
  markerSize?: number;
  clusteredMarkers: ReadonlyArray<ClusteredMarker<T>>;
  markerIcons?: Record<string, ImageSourcePropType>;
  clusterColor?: string;
  showUserPosition?: boolean;
  nightMode?: boolean;
  mapStyle?: string;
  onCameraPositionChange?: (event: NativeSyntheticEvent<CameraPosition>) => void;
  onCameraPositionChangeEnd?: (event: NativeSyntheticEvent<CameraPosition>) => void;
  onMapPress?: (event: NativeSyntheticEvent<Point>) => void;
  onMapLongPress?: (event: NativeSyntheticEvent<Point>) => void;
  onMapLoaded?: (event: NativeSyntheticEvent<MapLoaded>) => void;
  onMarkerPress?: (event: ClusteredMarkerPressEvent<T>) => void;
  userLocationAccuracyFillColor?: string;
  userLocationAccuracyStrokeColor?: string;
  userLocationAccuracyStrokeWidth?: number;
  scrollGesturesEnabled?: boolean;
  zoomGesturesEnabled?: boolean;
  tiltGesturesEnabled?: boolean;
  rotateGesturesEnabled?: boolean;
  fastTapEnabled?: boolean;
  initialRegion?: InitialRegion;
  maxFps?: number;
  followUser?: boolean;
  logoPosition?: YandexLogoPosition;
  logoPadding?: YandexLogoPadding;
}

type NativeClusteredMarker = {
  point: Point;
  data?: ClusteredMarkerData;
  iconKey?: string;
};

type NativeClusteredYaMapProps = Omit<
  ClusteredYaMapProps<ClusteredMarkerData>,
  'clusteredMarkers' | 'markerIcons' | 'userLocationIcon'
> & {
  clusteredMarkers: NativeClusteredMarker[];
  clusteredMarkerIcons?: Record<string, string>;
  userLocationIcon?: string;
  onRouteFound?: (event: NativeSyntheticEvent<{ id: string } & RoutesFoundEvent<DrivingInfo | MasstransitInfo>>) => void;
  onCameraPositionReceived?: (event: NativeSyntheticEvent<{ id: string } & CameraPosition>) => void;
  onVisibleRegionReceived?: (event: NativeSyntheticEvent<{ id: string } & VisibleRegion>) => void;
  onWorldToScreenPointsReceived?: (event: NativeSyntheticEvent<{ id: string } & ScreenPoint[]>) => void;
  onScreenToWorldPointsReceived?: (event: NativeSyntheticEvent<{ id: string } & Point[]>) => void;
};

const YaMapNativeComponent = requireNativeComponent<NativeClusteredYaMapProps>('ClusteredYamapView');

export class ClusteredYamap<T extends ClusteredMarkerData = ClusteredMarkerData> extends React.Component<ClusteredYaMapProps<T>> {
  static defaultProps = {
    showUserPosition: true,
    clusterColor: 'red',
    maxFps: 60,
    markerSize: 34
  };

  // @ts-ignore
  map = React.createRef<YaMapNativeComponent>();

  static ALL_MASSTRANSIT_VEHICLES: Vehicles[] = [
    'bus',
    'trolleybus',
    'tramway',
    'minibus',
    'suburban',
    'underground',
    'ferry',
    'cable',
    'funicular',
  ];

  public static init(apiKey: string): Promise<void> {
    return NativeYamapModule.init(apiKey);
  }

  public static setLocale(locale: string): Promise<void> {
    return new Promise((resolve, reject) => {
      NativeYamapModule.setLocale(locale, () => resolve(), (err: string) => reject(new Error(err)));
    });
  }

  public static getLocale(): Promise<string> {
    return new Promise((resolve, reject) => {
      NativeYamapModule.getLocale((locale: string) => resolve(locale), (err: string) => reject(new Error(err)));
    });
  }

  public static resetLocale(): Promise<void> {
    return new Promise((resolve, reject) => {
      NativeYamapModule.resetLocale(() => resolve(), (err: string) => reject(new Error(err)));
    });
  }

  public findRoutes(points: Point[], vehicles: Vehicles[], callback: (event: RoutesFoundEvent<DrivingInfo | MasstransitInfo>) => void) {
    this._findRoutes(points, vehicles, callback);
  }

  public findMasstransitRoutes(points: Point[], callback: (event: RoutesFoundEvent<MasstransitInfo>) => void) {
    this._findRoutes(points, YaMap.ALL_MASSTRANSIT_VEHICLES, callback);
  }

  public findPedestrianRoutes(points: Point[], callback: (event: RoutesFoundEvent<MasstransitInfo>) => void) {
    this._findRoutes(points, [], callback);
  }

  public findDrivingRoutes(points: Point[], callback: (event: RoutesFoundEvent<DrivingInfo>) => void) {
    this._findRoutes(points, ['car'], callback);
  }

  public fitAllMarkers() {
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('fitAllMarkers'),
      []
    );
  }

  public setTrafficVisible(isVisible: boolean) {
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('setTrafficVisible'),
      [isVisible]
    );
  }

  public fitMarkers(points: Point[]) {
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('fitMarkers'),
      [points]
    );
  }

  public setCenter(center: { lon: number, lat: number, zoom?: number }, zoom: number = center.zoom || 10, azimuth: number = 0, tilt: number = 0, duration: number = 0, animation: Animation = Animation.SMOOTH) {
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('setCenter'),
      [center, zoom, azimuth, tilt, duration, animation]
    );
  }

  public setZoom(zoom: number, duration: number = 0, animation: Animation = Animation.SMOOTH) {
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('setZoom'),
      [zoom, duration, animation]
    );
  }

  public getCameraPosition(callback: (position: CameraPosition) => void) {
    const cbId = CallbacksManager.addCallback(callback);
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('getCameraPosition'),
      [cbId]
    );
  }

  public getVisibleRegion(callback: (VisibleRegion: VisibleRegion) => void) {
    const cbId = CallbacksManager.addCallback(callback);
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('getVisibleRegion'),
      [cbId]
    );
  }

  public getScreenPoints(points: Point[], callback: (screenPoint: ScreenPoint) => void) {
    const cbId = CallbacksManager.addCallback(callback);
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('getScreenPoints'),
      [points, cbId]
    );
  }

  public getWorldPoints(points: ScreenPoint[], callback: (point: Point) => void) {
    const cbId = CallbacksManager.addCallback(callback);
    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('getWorldPoints'),
      [points, cbId]
    );
  }

  private _findRoutes(points: Point[], vehicles: Vehicles[], callback: ((event: RoutesFoundEvent<DrivingInfo | MasstransitInfo>) => void) | ((event: RoutesFoundEvent<DrivingInfo>) => void) | ((event: RoutesFoundEvent<MasstransitInfo>) => void)) {
    const cbId = CallbacksManager.addCallback(callback);
    const args = Platform.OS === 'ios' ? [{ points, vehicles, id: cbId }] : [points, vehicles, cbId];

    UIManager.dispatchViewManagerCommand(
      findNodeHandle(this),
      this.getCommand('findRoutes'),
      args
    );
  }

  private getCommand(cmd: string): any {
    return Platform.OS === 'ios' ? UIManager.getViewManagerConfig('ClusteredYamapView').Commands[cmd] : cmd;
  }

  private processRoute(event: NativeSyntheticEvent<{ id: string } & RoutesFoundEvent<DrivingInfo | MasstransitInfo>>) {
    const { id, ...routes } = event.nativeEvent;
    CallbacksManager.call(id, routes);
  }

  private processCameraPosition(event: NativeSyntheticEvent<{ id: string } & CameraPosition>) {
    const { id, ...point } = event.nativeEvent;
    CallbacksManager.call(id, point);
  }

  private processVisibleRegion(event: NativeSyntheticEvent<{ id: string } & VisibleRegion>) {
    const { id, ...visibleRegion } = event.nativeEvent;
    CallbacksManager.call(id, visibleRegion);
  }

  private processWorldToScreenPointsReceived(event: NativeSyntheticEvent<{ id: string } & ScreenPoint[]>) {
    const { id, ...screenPoints } = event.nativeEvent;
    CallbacksManager.call(id, screenPoints);
  }

  private processScreenToWorldPointsReceived(event: NativeSyntheticEvent<{ id: string } & Point[]>) {
    const { id, ...worldPoints } = event.nativeEvent;
    CallbacksManager.call(id, worldPoints);
  }

  private resolveImageUri(img: ImageSourcePropType) {
    return img ? resolveAssetSource(img).uri : '';
  }

  private resolveMarkerIcons(markerIcons?: Record<string, ImageSourcePropType>) {
    if (!markerIcons) {
      return undefined;
    }

    const resolvedEntries = Object.entries(markerIcons)
      .flatMap(([iconKey, imageSource]) => {
        const uri = this.resolveImageUri(imageSource);
        return uri ? [[iconKey, uri] as const] : [];
      });

    return resolvedEntries.length > 0 ? Object.fromEntries(resolvedEntries) : undefined;
  }

  private getProps(): NativeClusteredYaMapProps {
    const {
      clusteredMarkers,
      markerIcons,
      userLocationIcon,
      ...restProps
    } = this.props as ClusteredYaMapProps<ClusteredMarkerData>;

    const props: NativeClusteredYaMapProps = {
      ...restProps,
      clusteredMarkers: (clusteredMarkers ?? []).map(({ point, data, iconKey }) => ({
        point,
        data,
        iconKey,
      })),
      clusteredMarkerIcons: this.resolveMarkerIcons(markerIcons),
      onRouteFound: this.processRoute,
      onCameraPositionReceived: this.processCameraPosition,
      onVisibleRegionReceived: this.processVisibleRegion,
      onWorldToScreenPointsReceived: this.processWorldToScreenPointsReceived,
      onScreenToWorldPointsReceived: this.processScreenToWorldPointsReceived,
      userLocationIcon: userLocationIcon ? this.resolveImageUri(userLocationIcon) : undefined
    };

    processColorProps(props, 'clusterColor' as keyof NativeClusteredYaMapProps);
    processColorProps(props, 'userLocationAccuracyFillColor' as keyof NativeClusteredYaMapProps);
    processColorProps(props, 'userLocationAccuracyStrokeColor' as keyof NativeClusteredYaMapProps);

    return props;
  }

  render() {
    return (
      <YaMapNativeComponent
        {...this.getProps()}
        ref={this.map}
      />
    );
  }
}
