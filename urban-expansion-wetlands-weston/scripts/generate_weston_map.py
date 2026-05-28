# -*- coding: utf-8 -*-
"""
Urban Expansion vs Wetlands — Weston, Florida
==============================================
PyQGIS script to build a portfolio-ready QGIS project.

Tested with QGIS 3.44 (PyQGIS API using Qgis.* enums and QgsCoordinateReferenceSystem).

How to run:
  1. Open QGIS Desktop.
  2. Plugins → Python Console  (or Ctrl+Alt+P).
  3. Click "Show Editor", open this file, then click "Run Script".
     — OR run from the console:

     exec(open(r'D:/Panka/Trabalhos/QGIS/urban-expansion-wetlands-weston/scripts/build_weston_project.py', encoding='utf-8').read())

Outputs (created next to the project root):
  - output/weston_urban_wetlands.qgz
  - output/weston_urban_wetlands_map.png
  - screenshots/weston_map_overview.png  (copy for GitHub)
"""

import shutil
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsMapLayerType,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsPrintLayout,
    QgsProject,
    QgsFillSymbol,
    QgsRasterLayer,
    QgsRectangle,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QColor, QFont

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

# Web Mercator for project/basemap; sample inputs remain WGS84 lon/lat.
PROJECT_CRS = "EPSG:3857"
POINT_CRS = "EPSG:4326"  # input coordinates only

ESRI_SATELLITE_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)

# Sample points: (name, longitude, latitude) — portfolio demonstration data.
SAMPLE_POINTS = {
    "Urban / Residential": [
        ("Weston Town Center", -80.3805, 26.1072),
        ("Savanna Residential", -80.3650, 26.0880),
        ("Windmill Ranch Estates", -80.4200, 26.1150),
        ("Isles at Weston", -80.3950, 26.1250),
        ("Bonaventure Lakes", -80.3580, 26.1020),
    ],
    "Sports / Recreation": [
        ("Weston Regional Park", -80.3750, 26.1020),
        ("Tequesta Trace Park", -80.3880, 26.0950),
        ("Country Isles Park", -80.4020, 26.1080),
        ("Vista Park", -80.4120, 26.1180),
    ],
    "Water / Canal": [
        ("C-11 Canal (west segment)", -80.4100, 26.0900),
        ("Weston canal network", -80.3950, 26.0980),
        ("Bonaventure Lakes canal", -80.3650, 26.1050),
        ("South Florida Water Mgmt canal", -80.4350, 26.0850),
    ],
    "Wetlands / Natural Area": [
        ("Everglades edge (west)", -80.4500, 26.1000),
        ("Water Conservation Area 3A edge", -80.4800, 26.0800),
        ("Natural preserve (north Weston)", -80.4300, 26.1300),
        ("Wetland buffer — western boundary", -80.4650, 26.1100),
    ],
}

# Circular buffer radius in meters (EPSG:3857).
BUFFER_RADIUS_METERS = 500

CATEGORY_STYLE = {
    "Urban / Residential": {"color": "#e74c3c", "opacity": 0.90},
    "Sports / Recreation": {"color": "#f39c12", "opacity": 0.90},
    "Water / Canal": {"color": "#3498db", "opacity": 0.90},
    "Wetlands / Natural Area": {"color": "#27ae60", "opacity": 0.90},
}

# Drawing order: wetlands on bottom, urban on top.
LAYER_ORDER = [
    "Wetlands / Natural Area",
    "Water / Canal",
    "Sports / Recreation",
    "Urban / Residential",
]


# ---------------------------------------------------------------------------
# API HELPERS (QGIS 3.38+ / 3.44)
# ---------------------------------------------------------------------------

def make_field(name, variant_type):
    """
    Create a QgsField using QMetaType on QGIS 3.38+, with QVariant fallback.
    """
    try:
        from qgis.PyQt.QtCore import QMetaType

        type_map = {
            QVariant.String: QMetaType.Type.QString,
            QVariant.Double: QMetaType.Type.Double,
        }
        return QgsField(name, type_map[variant_type])
    except (AttributeError, KeyError, TypeError):
        return QgsField(name, variant_type)


def make_crs(auth_id):
    """Build and validate a QgsCoordinateReferenceSystem from an auth id."""
    crs = QgsCoordinateReferenceSystem(auth_id)
    if not crs.isValid():
        raise RuntimeError(f"Invalid CRS: {auth_id}")
    return crs


# ---------------------------------------------------------------------------
# STEP 1 — Prepare folders
# ---------------------------------------------------------------------------

def ensure_output_dirs():
    """Create output/ and screenshots/ if they do not exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# STEP 2 — New project and CRS
# ---------------------------------------------------------------------------

def create_new_project():
    """Clear the current session and set Web Mercator for the XYZ basemap."""
    project = QgsProject.instance()
    project.clear()
    project.setCrs(make_crs(PROJECT_CRS))
    print(f"[1/9] New project created | CRS: {PROJECT_CRS}")


# ---------------------------------------------------------------------------
# STEP 3 — Satellite basemap
# ---------------------------------------------------------------------------

def add_esri_satellite_basemap():
    """Add ESRI World Imagery as an XYZ tile layer."""
    uri = f"type=xyz&url={ESRI_SATELLITE_URL}&zmin=0&zmax=19"
    layer_name = "ESRI World Imagery (Satellite)"

    # QGIS 3.44: try dedicated xyz provider first, then legacy wms key.
    basemap = None
    for provider in ("xyz", "wms"):
        candidate = QgsRasterLayer(uri, layer_name, provider)
        if candidate.isValid():
            basemap = candidate
            break

    if basemap is None:
        raise RuntimeError(
            "Could not load ESRI satellite basemap. "
            "Check internet access and QGIS version (3.44 recommended)."
        )

    QgsProject.instance().addMapLayer(basemap)
    print("[2/9] Basemap added: ESRI World Imagery")
    return basemap


# ---------------------------------------------------------------------------
# STEP 4–6 — Vector layers (buffer polygons), styling, labels
# ---------------------------------------------------------------------------

def _category_fields():
    """Shared attribute fields for buffer polygon layers."""
    fields = QgsFields()
    fields.append(make_field("name", QVariant.String))
    fields.append(make_field("category", QVariant.String))
    fields.append(make_field("longitude", QVariant.Double))
    fields.append(make_field("latitude", QVariant.Double))
    return fields


def _wgs84_to_3857_transform():
    return QgsCoordinateTransform(
        make_crs("EPSG:4326"),
        make_crs("EPSG:3857"),
        QgsProject.instance().transformContext(),
    )


def create_buffer_layer(category_name, points):
    """
    Build an in-memory polygon layer: circular buffers around each sample point.
    Geometry is stored in EPSG:3857; lon/lat attributes remain WGS84.
    """
    layer = QgsVectorLayer(
        f"Polygon?crs={PROJECT_CRS}",
        category_name,
        "memory",
    )
    layer.dataProvider().addAttributes(_category_fields())
    layer.updateFields()

    transform = _wgs84_to_3857_transform()
    features = []

    for name, lon, lat in points:
        feat = QgsFeature(layer.fields())
        project_point = transform.transform(QgsPointXY(lon, lat))
        point_geom = QgsGeometry.fromPointXY(project_point)
        buffer_geom = point_geom.buffer(BUFFER_RADIUS_METERS, 24)
        feat.setGeometry(buffer_geom)
        feat.setAttributes([name, category_name, lon, lat])
        features.append(feat)

    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    return layer


def build_category_fill_symbol(color_hex, opacity):
    """Semi-transparent fill with white outline (reliable in layout export)."""
    symbol = QgsFillSymbol.createSimple({
        "color": color_hex,
        "outline_color": "#ffffff",
        "outline_width": "0.9",
        "style": "solid",
    })
    symbol.setOpacity(opacity)
    return symbol


def apply_buffer_style(layer, category_name):
    """Apply category fill color, white outline, and opacity to buffer polygons."""
    style = CATEGORY_STYLE[category_name]
    symbol = build_category_fill_symbol(style["color"], style["opacity"])
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def enable_polygon_labels(layer):
    """Label each buffer polygon using its 'name' attribute (centroid placement)."""
    settings = QgsPalLayerSettings()
    settings.fieldName = "name"
    settings.enabled = True

    text_format = settings.format()
    text_format.setFont(QFont("Segoe UI", 9))
    text_format.setColor(QColor("#ffffff"))
    text_format.buffer().setEnabled(True)
    text_format.buffer().setColor(QColor("#000000"))
    text_format.buffer().setSize(1.0)
    settings.setFormat(text_format)

    settings.placement = Qgis.LabelPlacement.AroundPoint
    settings.offsetType = Qgis.LabelOffsetType.FromPoint
    settings.offsetUnits = Qgis.RenderUnit.MapUnits
    settings.labelOffset = QgsPointXY(2.5, 2.5)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def add_all_vector_layers():
    """Create buffer polygons, style, label, and add layers above the basemap."""
    layers = []

    for category_name in LAYER_ORDER:
        points = SAMPLE_POINTS.get(category_name, [])
        layer = create_buffer_layer(category_name, points)
        apply_buffer_style(layer, category_name)
        enable_polygon_labels(layer)
        QgsProject.instance().addMapLayer(layer)
        layers.append(layer)
        print(
            f"[3-6/9] Layer: {category_name} "
            f"({layer.featureCount()} buffers, styled & labeled)"
        )

    return layers


# ---------------------------------------------------------------------------
# STEP 7 — Map extent (Weston study area)
# ---------------------------------------------------------------------------

def zoom_to_weston():
    """Compute and apply a map extent covering all sample points."""
    all_lons, all_lats = [], []
    for pts in SAMPLE_POINTS.values():
        for _, lon, lat in pts:
            all_lons.append(lon)
            all_lats.append(lat)

    pad_x = (max(all_lons) - min(all_lons)) * 0.15 or 0.01
    pad_y = (max(all_lats) - min(all_lats)) * 0.15 or 0.01

    rect_wgs84 = QgsRectangle(
        min(all_lons) - pad_x,
        min(all_lats) - pad_y,
        max(all_lons) + pad_x,
        max(all_lats) + pad_y,
    )

    transform = QgsCoordinateTransform(
        make_crs(POINT_CRS),
        make_crs(PROJECT_CRS),
        QgsProject.instance().transformContext(),
    )
    extent = transform.transformBoundingBox(rect_wgs84)

    # QGIS 3.44: setDefaultViewExtent() requires QgsReferencedRectangle, not
    # QgsRectangle. Zoom the active map canvas instead (run from Python Console).
    from qgis.utils import iface

    if iface and iface.mapCanvas():
        canvas = iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()
    else:
        print(
            "[7/9] Warning: map canvas unavailable — extent not applied to the view "
            "(run this script from the QGIS Python Console)."
        )

    print("[7/9] Map extent set to Weston, Florida")
    return extent


# ---------------------------------------------------------------------------
# STEP 8 — Print layout and PNG export
# ---------------------------------------------------------------------------

def create_print_layout(extent):
    """Build an A4 landscape layout with title, map, legend, and credits."""
    project = QgsProject.instance()
    layout_name = "Weston Urban vs Wetlands Map"

    manager = project.layoutManager()
    for existing in manager.layouts():
        if existing.name() == layout_name:
            manager.removeLayout(existing)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)
    manager.addLayout(layout)

    page = layout.pageCollection().page(0)
    page.setPageSize("A4", QgsLayoutItemPage.Landscape)

    title = QgsLayoutItemLabel(layout)
    title.setText("Urban Expansion vs Wetlands — Weston, Florida")
    title.setFont(QFont("Segoe UI", 18, QFont.Bold))
    title.adjustSizeToText()
    title.attemptMove(QgsLayoutPoint(15, 10, Qgis.LayoutUnit.Millimeters))
    layout.addLayoutItem(title)

    subtitle = QgsLayoutItemLabel(layout)
    subtitle.setText(
        "Suburban development, recreation, canals, and wetland edges | "
        "EPSG:3857 | ESRI World Imagery"
    )
    subtitle.setFont(QFont("Segoe UI", 9))
    subtitle.adjustSizeToText()
    subtitle.attemptMove(QgsLayoutPoint(15, 22, Qgis.LayoutUnit.Millimeters))
    layout.addLayoutItem(subtitle)

    # Map item — QGIS 3.44: setRect, add to layout, move/resize, then layers & extent.
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(20, 20, 200, 100)
    layout.addLayoutItem(map_item)

    map_item.attemptMove(QgsLayoutPoint(15, 32, Qgis.LayoutUnit.Millimeters))
    map_item.attemptResize(QgsLayoutSize(260, 165, Qgis.LayoutUnit.Millimeters))

    all_layers = list(QgsProject.instance().mapLayers().values())
    basemap_layers = [
        layer for layer in all_layers if layer.type() == QgsMapLayerType.RasterLayer
    ]
    vector_layers = [
        layer for layer in all_layers if layer.type() == QgsMapLayerType.VectorLayer
    ]
    # QgsLayoutItemMap setLayers order: first = top, last = bottom
    map_item.setLayers(vector_layers + basemap_layers)

    map_item.setExtent(extent)

    map_item.setFrameEnabled(True)
    map_item.refresh()
    layout.refresh()

    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Land Use Categories")
    legend.setLinkedMap(map_item)
    legend.setBackgroundEnabled(True)
    legend.attemptMove(QgsLayoutPoint(215, 32, Qgis.LayoutUnit.Millimeters))
    legend.attemptResize(QgsLayoutSize(70, 90, Qgis.LayoutUnit.Millimeters))
    layout.addLayoutItem(legend)

    credits = QgsLayoutItemLabel(layout)
    credits.setText(
        "Sample points (portfolio demo) | Basemap: ESRI World Imagery | "
        "Built with PyQGIS"
    )
    credits.setFont(QFont("Segoe UI", 7))
    credits.adjustSizeToText()
    credits.attemptMove(QgsLayoutPoint(15, 200, Qgis.LayoutUnit.Millimeters))
    layout.addLayoutItem(credits)

    print("[8/9] Print layout created")
    return layout


def export_layout_png(layout):
    """Export the layout to a 300 DPI PNG in output/."""
    png_path = OUTPUT_DIR / "weston_urban_wetlands_map.png"
    exporter = QgsLayoutExporter(layout)

    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = 300

    # Allow XYZ basemap tiles to finish loading before export.
    QCoreApplication.processEvents()

    result = exporter.exportToImage(str(png_path), settings)
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(f"PNG export failed (code {result})")

    dst = SCREENSHOTS_DIR / "weston_map_overview.png"
    shutil.copy2(png_path, dst)
    print(f"[8/9] Map exported: {png_path}")
    print(f"        Screenshot copy: {dst}")
    return png_path


# ---------------------------------------------------------------------------
# STEP 9 — Save QGIS project
# ---------------------------------------------------------------------------

def save_project():
    """Save the project as a .qgz file."""
    qgz_path = OUTPUT_DIR / "weston_urban_wetlands.qgz"
    if not QgsProject.instance().write(str(qgz_path)):
        raise RuntimeError("Failed to save QGIS project (.qgz).")
    print(f"[9/9] Project saved: {qgz_path}")
    return qgz_path


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    """Execute all portfolio build steps in order."""
    print("=" * 60)
    print("Urban Expansion vs Wetlands — Weston, Florida")
    print("=" * 60)

    ensure_output_dirs()
    create_new_project()
    add_esri_satellite_basemap()
    QCoreApplication.processEvents()
    add_all_vector_layers()
    extent = zoom_to_weston()
    layout = create_print_layout(extent)
    export_layout_png(layout)
    save_project()

    print("=" * 60)
    print("Complete. Open output/weston_urban_wetlands.qgz in QGIS.")
    print("=" * 60)


main()
