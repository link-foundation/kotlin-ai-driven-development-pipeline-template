package template

import kotlin.test.Test
import kotlin.test.assertEquals

class GreetingTest {
    @Test
    fun greetsKotlinByDefault() {
        assertEquals("Hello, Kotlin!", greeting())
        assertEquals("Hello, Kotlin!", greeting("  "))
    }

    @Test
    fun trimsTheSuppliedName() {
        assertEquals("Hello, Ada!", greeting(" Ada "))
    }
}
