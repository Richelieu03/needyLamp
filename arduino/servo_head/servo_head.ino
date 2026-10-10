#include <Servo.h>

const int SERVO_PIN = 9;
const int MIN_ANGLE = 30;      // keep away from the mechanical end stops
const int MAX_ANGLE = 150;
const int STEP_DELAY_MS = 12;  // smaller = faster glide

Servo head;
int current = 90;              // where the servo is now
int target = 90;               // where we want it to be

void setup() {
  Serial.begin(115200);
  head.attach(SERVO_PIN);
  head.write(current);         // start centered
}

void loop() {
  // Read a new target if one has arrived, e.g. "120\n"
  if (Serial.available()) {
    int angle = Serial.parseInt();
    if (Serial.read() == '\n') {
      target = constrain(angle, MIN_ANGLE, MAX_ANGLE);
    }
  }

  // Move one degree at a time toward the target for a smooth turn
  if (current != target) {
    current += (target > current) ? 1 : -1;
    head.write(current);
    delay(STEP_DELAY_MS);
  }
}