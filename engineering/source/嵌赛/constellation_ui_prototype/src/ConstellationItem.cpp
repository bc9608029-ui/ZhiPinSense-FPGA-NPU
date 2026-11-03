// ConstellationItem.cpp — scene-graph renderer for the IQ scatter.
#include "ConstellationItem.hpp"

#include <QtQuick/QSGGeometry>
#include <QtQuick/QSGGeometryNode>
#include <QtQuick/QSGVertexColorMaterial>

#include <algorithm>

namespace {
// One quad per point (4 vertices, 6 indices). 4096 points -> 16384 vertices,
// which stays comfortably inside the 16-bit index range (65535).
constexpr int kVertsPerPoint = 4;
constexpr int kIndicesPerPoint = 6;
}  // namespace

ConstellationItem::ConstellationItem(QQuickItem* parent) : QQuickItem(parent) {
    setFlag(ItemHasContents, true);
}

ConstellationItem::~ConstellationItem() = default;

void ConstellationItem::setPointSize(qreal s) {
    s = std::max<qreal>(1.0, s);
    if (qFuzzyCompare(s, pointSize_)) return;
    pointSize_ = s;
    emit pointSizeChanged();
    update();
}

void ConstellationItem::setPoints(const QVector<QPointF>& pts,
                                  const QVector<QColor>& colors) {
    pts_ = pts;
    colors_ = colors;
    emit pointCountChanged();
    update();
}

void ConstellationItem::clearPoints() {
    pts_.clear();
    colors_.clear();
    emit pointCountChanged();
    update();
}

QSGNode* ConstellationItem::updatePaintNode(QSGNode* oldNode, UpdatePaintNodeData*) {
    QSGGeometryNode* node = static_cast<QSGGeometryNode*>(oldNode);
    if (!node) {
        node = new QSGGeometryNode();
        node->setMaterial(new QSGVertexColorMaterial());
        node->setFlag(QSGNode::OwnsMaterial);
    }

    const int n = pts_.size();
    QSGGeometry* g = node->geometry();
    if (!g) {
        g = new QSGGeometry(QSGGeometry::defaultAttributes_ColoredPoint2D(),
                            kVertsPerPoint * n, kIndicesPerPoint * n,
                            QSGGeometry::UnsignedShortType);
        node->setGeometry(g);
        node->setFlag(QSGNode::OwnsGeometry);
    } else {
        g->allocate(kVertsPerPoint * n, kIndicesPerPoint * n);
    }
    g->setDrawingMode(QSGGeometry::DrawTriangles);

    if (n == 0) {
        node->setGeometry(g);
        node->markDirty(QSGNode::DirtyGeometry);
        return node;
    }

    // Letterbox into the largest centered square so I and Q share one scale.
    const qreal side = std::min(width(), height());
    const qreal ox = (width() - side) / 2.0;
    const qreal oy = (height() - side) / 2.0;
    const qreal half = pointSize_ / 2.0;

    QSGGeometry::ColoredPoint2D* v = g->vertexDataAsColoredPoint2D();
    quint16* idx = g->indexDataAsUShort();

    for (int i = 0; i < n; ++i) {
        const qreal cx = ox + pts_.at(i).x() * side;
        const qreal cy = oy + pts_.at(i).y() * side;
        const QColor c = i < colors_.size() ? colors_.at(i) : QColor(200, 200, 200);
        const uchar r = static_cast<uchar>(c.red());
        const uchar gg = static_cast<uchar>(c.green());
        const uchar b = static_cast<uchar>(c.blue());
        const uchar a = static_cast<uchar>(c.alpha());

        const int base = i * kVertsPerPoint;
        v[base + 0].set(cx - half, cy - half, r, gg, b, a);
        v[base + 1].set(cx + half, cy - half, r, gg, b, a);
        v[base + 2].set(cx + half, cy + half, r, gg, b, a);
        v[base + 3].set(cx - half, cy + half, r, gg, b, a);

        const int ib = i * kIndicesPerPoint;
        idx[ib + 0] = static_cast<quint16>(base + 0);
        idx[ib + 1] = static_cast<quint16>(base + 1);
        idx[ib + 2] = static_cast<quint16>(base + 2);
        idx[ib + 3] = static_cast<quint16>(base + 0);
        idx[ib + 4] = static_cast<quint16>(base + 2);
        idx[ib + 5] = static_cast<quint16>(base + 3);
    }

    // Geometry was rewritten in place (vertices + indices, and per-vertex colors
    // live in the geometry too), so the node must be re-uploaded. The material is
    // a constant QSGVertexColorMaterial and never changes after creation; item
    // opacity is handled by QQuickItem, so DirtyGeometry is the only flag needed.
    node->markDirty(QSGNode::DirtyGeometry);

    return node;
}
