const toggleIcon = (e) => 
{
  e.target.classList.toggle('active');
};

$('.arrow').on('mouseover', toggleIcon);
$('.arrow').on('mouseout', toggleIcon);

var ellipseAngle = 60;
var childAngle = 90;
var heightCorrector = 2.0; //Used to make the island images appear vertical even though they are actually angled in 3D slightly
var isle1opacity = 1.0; 
var isle1Angle = 0; 


$( '#rightArrow' ).click(function() 
{ 
  isle1Angle -= 90;
  updateIslandOpacity("right");
  updateIslandRotation("right");
});

$( '#leftArrow' ).click(function()
{ 
  isle1Angle += 90;
  updateIslandOpacity("left");
  updateIslandRotation("left");
});

function updateIslandRotation(direction)
{
  $("#parent1").css({ transform: 'rotateX(' + ellipseAngle + 'deg) rotateZ(' + isle1Angle + 'deg)' });
  $(".island").css({ transform: 'rotateZ(' + childAngle + 'deg) scaleY(' + heightCorrector + ')'  });
  childAngle += 90;
  /*Problem: opacity transitions don't speed up when the user clicks rapdily, speeding up rotation.  
  /* --May need to figure out another method to do this.*/
 }

var fadeSpeed = 1700;
var rect1, rect2, rect3, rect4;
var opValue1, opValue2, opValue3, opValue4;

function getOpScalar(rect)
{
   // ToDO Change 33 and 400 to screen percentages for multiple display formats
  var value = rect.top + window.scrollY; //Use object's position to set opacity
  value = (value - 33)/400; //Shift and scale range to be 0.0-0.5
  value = (1 - value) - 0.55;  //Invert and shift values due to the way opacity works in css i.e. 0 is fully transparent
  return value;
}

function updateIslandOpacity(direction){ 
  /* update island bounding rectangles*/
  rect1 = document.getElementById('island1').getBoundingClientRect();
  rect2 = document.getElementById('island2').getBoundingClientRect();
  rect3 = document.getElementById('island3').getBoundingClientRect();
  rect4 = document.getElementById('island4').getBoundingClientRect();
  
  /*Islands use the adjacent island position on click to set their next opacity target*/
  opValue1 = getOpScalar(rect2);
  opValue2 = getOpScalar(rect3);
  opValue3 = getOpScalar(rect4);
  opValue4 = getOpScalar(rect1);

  //console.log(opValue1);
  //Adjust the transparency of the atmospheric perspective copy of the island image
  if (direction == "right")
  {
    /*Islands use the adjacent island position on click to set their next opacity target*/
    opValue1 = getOpScalar(rect2);
    opValue2 = getOpScalar(rect3);
    opValue3 = getOpScalar(rect4);
    opValue4 = getOpScalar(rect1);
  } 
  else 
  { 
    if (direction == "left")
    {
      /*Islands use the adjacent island position on click to set their next opacity target*/
      opValue1 = getOpScalar(rect4);
      opValue2 = getOpScalar(rect1);
      opValue3 = getOpScalar(rect2);
      opValue4 = getOpScalar(rect3);
    }
  }
  $("#island1persp").fadeTo(fadeSpeed, opValue1);
  $("#island2persp").fadeTo(fadeSpeed, opValue2);
  $("#island3persp").fadeTo(fadeSpeed, opValue3);
  $("#island4persp").fadeTo(fadeSpeed, opValue4);
}


$('#island1persp' ).on('mouseover',toggleIcon); 
$('#island1persp').on('mouseout', toggleIcon);
