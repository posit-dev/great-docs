# Widget

A widget that spins.

Usage

``` python
Widget(speed=1)
```

Widgets spin in place until stopped.

## Parameters

`speed: int = 1`  
How fast the widget spins.

## Methods

| Name            | Description       |
|-----------------|-------------------|
| [spin()](Widget.spin.md) | Spin the widget. |
| [stop()](#stop) | Stop the widget.  |

### stop()

Stop the widget.

Usage

``` python
Widget.stop(now=False)
```

#### Returns

`bool`  
Whether the widget was spinning.

## Examples

``` python
Widget(speed=2).spin()
```
