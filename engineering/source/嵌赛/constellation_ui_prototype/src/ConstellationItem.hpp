// ConstellationItem.hpp — C++ QQuickItem scatter render component.
//
// The high-frequency constellation points are drawn by this C++ scene-graph
// node (QSGGeometryNode + QSGVertexColorMaterial), NOT by QML JavaScript and
// NOT by a Canvas. The renderer receives already-decimated, already-transformed
// points in unit coordinates ([0,1]^2, y-down); all parsing / SHA / decimation /
// auto-scale math lives in the Qt-free IqFrame.hpp / IqFrameLoader.cpp.
#pragma once

#include <QColor>
#include <QPointF>
#include <QQuickItem>
#include <QVector>

class ConstellationItem : public QQuickItem {
    Q_OBJECT
    Q_PROPERTY(qreal pointSize READ pointSize WRITE setPointSize NOTIFY pointSizeChanged)
    Q_PROPERTY(int pointCount READ pointCount NOTIFY pointCountChanged)

public:
    explicit ConstellationItem(QQuickItem* parent = nullptr);
    ~ConstellationItem() override;

    qreal pointSize() const { return pointSize_; }
    void setPointSize(qreal s);

    int pointCount() const { return pts_.size(); }

    // Points are in unit coordinates [0,1]^2 (y increasing downward); the item
    // letterboxes them into the largest centered square so I and Q keep an
    // identical scale. `colors` has one entry per point (stage color, or red for
    // out-of-range points). Called from C++ (never per-point from QML).
    void setPoints(const QVector<QPointF>& pts, const QVector<QColor>& colors);
    void clearPoints();

signals:
    void pointSizeChanged();
    void pointCountChanged();

protected:
    QSGNode* updatePaintNode(QSGNode* oldNode, UpdatePaintNodeData*) override;

private:
    QVector<QPointF> pts_;
    QVector<QColor> colors_;
    qreal pointSize_ = 2.0;
};
